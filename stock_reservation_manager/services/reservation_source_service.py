from odoo import api, models, _


class ReservationSourceService(models.AbstractModel):
    _name = "stock.reservation.source.service"
    _description = "Reservation Source Document Resolver"

    @api.model
    def resolve(self, move):
        candidates = [
            ("sale_line_id", "sale.order", "order_id", _("Sales Order")),
            ("production_id", "mrp.production", None, _("Manufacturing Order")),
            ("raw_material_production_id", "mrp.production", None, _("Manufacturing Order")),
            ("repair_id", "repair.order", None, _("Repair Order")),
        ]
        for field_name, model_name, parent_field, label in candidates:
            if field_name not in move._fields:
                continue
            record = move[field_name]
            if record and parent_field:
                record = record[parent_field]
            if record:
                return {"model": model_name, "id": record.id, "label": label,
                        "reference": record.display_name}
        if move.picking_id:
            return {"model": "stock.picking", "id": move.picking_id.id,
                    "label": _("Inventory Transfer"), "reference": move.picking_id.display_name}
        return {"model": "stock.move", "id": move.id, "label": _("Stock Move"),
                "reference": move.reference or move.origin or move.display_name}
