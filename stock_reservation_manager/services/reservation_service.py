from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


ACTIVE_STATES = ["confirmed", "waiting", "partially_available", "assigned"]


class ReservationService(models.AbstractModel):
    _name = "stock.reservation.service"
    _description = "Native Stock Reservation Query Service"

    @api.model
    def _company_ids(self, filters):
        allowed = set(self.env.companies.ids)
        requested = set(filters.get("company_ids") or allowed)
        if not requested.issubset(allowed):
            raise AccessError(_("You cannot access reservation data for the selected company."))
        return list(requested)

    @api.model
    def _move_domain(self, filters, demand=True):
        domain = [("company_id", "in", self._company_ids(filters)), ("state", "in", ACTIVE_STATES)]
        if demand:
            domain.append(("product_uom_qty", ">", 0))
        if filters.get("warehouse_id"):
            warehouse = self.env["stock.warehouse"].browse(filters["warehouse_id"]).exists()
            domain.append(("location_id", "child_of", warehouse.view_location_id.id))
        for key, field_name in (("product_id", "product_id"), ("location_id", "location_id"),
                                ("picking_id", "picking_id"), ("customer_id", "partner_id")):
            if filters.get(key):
                domain.append((field_name, "=", filters[key]))
        if filters.get("search"):
            value = filters["search"]
            domain += ["|", "|", "|", ("product_id", "ilike", value),
                       ("product_id.default_code", "ilike", value),
                       ("picking_id.name", "ilike", value), ("origin", "ilike", value)]
        return domain

    @api.model
    def _line_domain(self, filters):
        move_domain = self._move_domain(filters, False)
        nested = [("move_id." + item[0], item[1], item[2])
                  if isinstance(item, (tuple, list)) else item for item in move_domain]
        return [("quantity_product_uom", ">", 0), ("picked", "=", False)] + nested

    @api.model
    def get_dashboard(self, filters, tab, offset, limit):
        line_domain = self._line_domain(filters)
        move_domain = self._move_domain(filters)
        line_groups = self.env["stock.move.line"]._read_group(
            line_domain, ["product_id"], ["quantity_product_uom:sum", "__count"])
        reserved_by_product = {product.id: (quantity, count) for product, quantity, count in line_groups}
        move_groups = self.env["stock.move"]._read_group(
            move_domain, ["product_id"], ["product_uom_qty:sum", "quantity:sum", "__count"])
        partial = sum(1 for _product, demand, reserved, _count in move_groups if reserved > 0 and reserved < demand)
        unreserved = sum(1 for _product, demand, reserved, _count in move_groups if demand > 0 and not reserved)
        quant_domain = [("company_id", "in", self._company_ids(filters)), ("location_id.usage", "=", "internal")]
        if filters.get("warehouse_id"):
            warehouse = self.env["stock.warehouse"].browse(filters["warehouse_id"])
            quant_domain.append(("location_id", "child_of", warehouse.view_location_id.id))
        quant_groups = self.env["stock.quant"]._read_group(
            quant_domain, ["product_id"], ["quantity:sum", "reserved_quantity:sum"])
        quant_by_product = {product.id: (quantity, reserved) for product, quantity, reserved in quant_groups}
        fully_reserved = sum(1 for _product, demand, reserved, _count in move_groups if demand > 0 and reserved >= demand)
        old_date = fields.Datetime.now() - timedelta(days=self.env.company.reservation_old_days)
        old_groups = self.env["stock.move.line"]._read_group(line_domain + [("date", "<", old_date)], [], ["__count"])
        old_count = old_groups[0][0] if old_groups else 0
        conflicts = (self.env["stock.reservation.analysis.service"].conflicts(
            self._company_ids(filters), filters.get("warehouse_id"), 200)
            if self.env.company.reservation_conflict_enabled else [])
        kpis = {"products": len(reserved_by_product), "reserved": sum(value[0] for value in reserved_by_product.values()),
                "fully_reserved": fully_reserved, "partial": partial, "unreserved": unreserved,
                "old": old_count, "conflicts": len(conflicts), "due_soon": self._due_soon(move_domain)}
        if tab == "conflict":
            rows = conflicts[offset:offset + limit]
        elif tab == "aging":
            rows = self.env["stock.reservation.analysis.service"].aging_buckets(line_domain)
        elif tab in ("partial", "unreserved", "transaction"):
            rows = self._move_rows(move_domain, tab, offset, limit)
        elif tab == "customer":
            rows = self._customer_rows(move_domain, offset, limit)
        elif tab == "warehouse":
            rows = self._warehouse_rows(filters, offset, limit)
        else:
            rows = self._product_rows(reserved_by_product, quant_by_product, offset, limit)
        return {"kpis": kpis, "rows": rows, "offset": offset, "limit": limit, "tab": tab,
                "age_is_estimated": True, "manager": self.env.user.has_group("stock.group_stock_manager")}

    @api.model
    def _product_rows(self, reserved, quants, offset, limit):
        product_ids = list(reserved)[offset:offset + limit]
        products = {product.id: product for product in self.env["product.product"].browse(product_ids)}
        rows = []
        for product_id in product_ids:
            quantity, quant_reserved = quants.get(product_id, (0, 0))
            line_reserved, count = reserved[product_id]
            ratio = 100 * quant_reserved / quantity if quantity > 0 else (100 if quant_reserved else 0)
            rows.append({"id": product_id, "product_id": product_id, "product": products[product_id].display_name,
                         "default_code": products[product_id].default_code or "", "on_hand": quantity,
                         "reserved": quant_reserved, "free": quantity - quant_reserved,
                         "reservation_count": count, "line_reserved": line_reserved, "ratio": ratio,
                         "status": "critical" if ratio >= self.env.company.reservation_critical_percent else "available"})
        return rows

    @api.model
    def _move_rows(self, domain, tab, offset, limit):
        domain = list(domain)
        if tab == "partial":
            domain += [("quantity", ">", 0), ("state", "=", "partially_available")]
        elif tab == "unreserved":
            domain += [("quantity", "=", 0)]
        moves = self.env["stock.move"].search(domain, order="priority desc, date asc, id", offset=offset, limit=limit)
        resolver = self.env["stock.reservation.source.service"]
        return [{"id": move.id, "product_id": move.product_id.id, "product": move.product_id.display_name,
                 "reference": move.picking_id.name or move.reference, "origin": move.origin or "",
                 "demand": move.product_uom_qty, "reserved": move.quantity,
                 "missing": max(move.product_uom_qty - move.quantity, 0), "date": move.date,
                 "priority": move.priority, "state": move.state, "source": resolver.resolve(move)} for move in moves]

    @api.model
    def _customer_rows(self, domain, offset, limit):
        # In Odoo 17 stock.move.line.picking_partner_id is a non-stored related
        # field and therefore cannot be converted to SQL for _read_group().
        # stock.move.partner_id is stored and represents the same destination
        # partner for reservation reporting.
        groups = self.env["stock.move"]._read_group(
            domain + [("partner_id", "!=", False), ("quantity", ">", 0)], ["partner_id"],
            ["quantity:sum", "product_id:count_distinct", "picking_id:count_distinct"],
            offset=offset, limit=limit, order="quantity:sum desc")
        return [{"id": partner.id, "customer": partner.display_name, "reserved": quantity,
                 "products": products, "transfers": transfers}
                for partner, quantity, products, transfers in groups]

    @api.model
    def _warehouse_rows(self, filters, offset, limit):
        warehouses = self.env["stock.warehouse"].search(
            [("company_id", "in", self._company_ids(filters))], offset=offset, limit=limit)
        rows = []
        for warehouse in warehouses:
            groups = self.env["stock.quant"]._read_group(
                [("location_id", "child_of", warehouse.view_location_id.id), ("location_id.usage", "=", "internal")],
                [], ["quantity:sum", "reserved_quantity:sum"])
            quantity, reserved = groups[0] if groups else (0, 0)
            rows.append({"id": warehouse.id, "warehouse": warehouse.display_name, "on_hand": quantity,
                         "reserved": reserved, "free": quantity - reserved,
                         "ratio": 100 * reserved / quantity if quantity > 0 else 0})
        return rows

    @api.model
    def _due_soon(self, domain):
        end = fields.Datetime.now() + timedelta(days=2)
        groups = self.env["stock.move"]._read_group(list(domain) + [("date", "<=", end), ("quantity", ">", 0)], [], ["__count"])
        return groups[0][0] if groups else 0

    @api.model
    def get_product_details(self, product_id, filters, offset, limit):
        product = self.env["product.product"].browse(product_id).exists()
        if not product:
            raise UserError(_("The product no longer exists."))
        domain = self._line_domain(dict(filters, product_id=product_id))
        lines = self.env["stock.move.line"].search(domain, order="date asc, id", offset=offset, limit=limit)
        resolver = self.env["stock.reservation.source.service"]
        return {"product_id": product.id, "product": product.display_name, "lines": [{"id": line.id, "move_id": line.move_id.id,
            "picking_id": line.picking_id.id, "picking": line.picking_id.name or "", "origin": line.origin or "",
            "source": resolver.resolve(line.move_id), "source_location": line.location_id.display_name,
            "destination_location": line.location_dest_id.display_name, "reserved": line.quantity_product_uom,
            "line_quantity": line.quantity,
            "demand": line.move_id.product_uom_qty, "date": line.move_id.date, "reservation_date": line.date,
            "age_days": max((fields.Datetime.now() - line.date).days, 0), "age_exact": False,
            "priority": line.move_id.priority, "state": line.state, "lot": line.lot_id.name or "",
            "package": line.package_id.display_name or "", "owner": line.owner_id.display_name or ""} for line in lines]}

    @api.model
    def check_availability(self, move_id):
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(_("Only Reservation Control Managers can check availability from this control center."))
        move = self.env["stock.move"].browse(move_id).exists()
        if not move or move.company_id not in self.env.companies:
            raise AccessError(_("You cannot access this stock move."))
        before = move.quantity
        move._action_assign()
        source = self.env["stock.reservation.source.service"].resolve(move)
        self.env["stock.reservation.audit"].create({"company_id": move.company_id.id,
            "action_type": "check_availability", "product_id": move.product_id.id,
            "picking_id": move.picking_id.id, "move_id": move.id, "quantity_before": before,
            "quantity_changed": move.quantity - before, "quantity_after": move.quantity,
            "source_document_model": source["model"], "source_document_id": source["id"],
            "source_document_reference": source["reference"],
            "reason": _("Check Availability from Reservation Manager")})
        return {"reserved": move.quantity, "state": move.state}
