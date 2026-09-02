from datetime import timedelta

from odoo import api, fields, models


class ReservationAnalysisService(models.AbstractModel):
    _name = "stock.reservation.analysis.service"
    _description = "Reservation Aging and Conflict Analysis"

    @api.model
    def aging_buckets(self, line_domain):
        values = {int(value.strip()) for company in self.env.companies
                  for value in (company.reservation_aging_buckets or "").split(",")
                  if value.strip().isdigit() and int(value.strip()) > 0}
        boundaries = sorted(values) or [1, 3, 7, 15, 30]
        now = fields.Datetime.now()
        rows = []
        previous = 0
        for boundary in boundaries:
            domain = list(line_domain) + [
                ("date", "<", now - timedelta(days=previous)),
                ("date", ">=", now - timedelta(days=boundary)),
            ]
            groups = self.env["stock.move.line"]._read_group(domain, [], ["quantity_product_uom:sum", "__count"])
            quantity, count = groups[0] if groups else (0, 0)
            rows.append({"id": f"{previous}-{boundary}", "label": f"{previous}-{boundary} days",
                         "quantity": quantity, "count": count})
            previous = boundary
        domain = list(line_domain) + [("date", "<", now - timedelta(days=previous))]
        groups = self.env["stock.move.line"]._read_group(domain, [], ["quantity_product_uom:sum", "__count"])
        quantity, count = groups[0] if groups else (0, 0)
        rows.append({"id": f"{previous}+", "label": f"{previous}+ days", "quantity": quantity, "count": count})
        return rows

    @api.model
    def conflicts(self, company_ids, warehouse_id=False, limit=200):
        move_domain = [("company_id", "in", company_ids), ("state", "in", ["confirmed", "waiting", "partially_available", "assigned"]),
                       ("product_uom_qty", ">", 0)]
        quant_domain = [("company_id", "in", company_ids), ("location_id.usage", "=", "internal")]
        if warehouse_id:
            warehouse = self.env["stock.warehouse"].browse(warehouse_id).exists()
            move_domain.append(("location_id", "child_of", warehouse.view_location_id.id))
            quant_domain.append(("location_id", "child_of", warehouse.view_location_id.id))
        move_groups = self.env["stock.move"]._read_group(move_domain, ["product_id"],
                                                          ["product_uom_qty:sum", "quantity:sum", "__count"])
        quant_groups = self.env["stock.quant"]._read_group(quant_domain, ["product_id"], ["quantity:sum"])
        available = {product.id: quantity for product, quantity in quant_groups}
        rows = []
        for product, demand, reserved, count in move_groups:
            on_hand = available.get(product.id, 0)
            if count > 1 and demand > on_hand:
                rows.append({"id": product.id, "product_id": product.id, "product": product.display_name,
                             "demand": demand, "reserved": reserved, "missing": max(demand - on_hand, 0),
                             "conflict": "Demand exceeds available stock"})
            if len(rows) >= limit:
                break
        return rows
