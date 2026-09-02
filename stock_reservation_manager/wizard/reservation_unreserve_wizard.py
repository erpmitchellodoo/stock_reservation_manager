from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare


class ReservationUnreserveWizard(models.TransientModel):
    _name = "stock.reservation.unreserve.wizard"
    _description = "Confirm Native Reservation Release"

    move_line_ids = fields.Many2many("stock.move.line", required=True)
    quantity_to_release = fields.Float(digits="Product Unit")
    current_quantity = fields.Float(compute="_compute_summary")
    company_id = fields.Many2one("res.company", compute="_compute_summary")
    reason_required = fields.Boolean(compute="_compute_summary")
    reason = fields.Selection([("priority", "Higher Priority Order"), ("delay", "Customer Delay"),
        ("payment", "Payment Pending"), ("hold", "Order On Hold"), ("incorrect", "Incorrect Reservation"),
        ("reallocation", "Stock Reallocation"), ("manager", "Manager Decision"), ("other", "Other")])
    notes = fields.Text()
    snapshot = fields.Json(readonly=True)

    @api.depends("move_line_ids")
    def _compute_summary(self):
        for wizard in self:
            wizard.current_quantity = sum(wizard.move_line_ids.mapped("quantity_product_uom"))
            companies = wizard.move_line_ids.company_id
            wizard.company_id = companies if len(companies) == 1 else False
            wizard.reason_required = bool(wizard.company_id.reservation_require_unreserve_reason)

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(_("Only Reservation Control Managers can unreserve stock."))
        lines = self.move_line_ids.exists()
        if not lines or len(lines.company_id) != 1 or lines.company_id not in self.env.companies:
            raise AccessError(_("Reservations must belong to one authorized company."))
        if not lines.company_id.reservation_unreserve_enabled:
            raise UserError(_("Manual unreserve is disabled for this company."))
        if lines.company_id.reservation_require_unreserve_reason and not self.reason:
            raise UserError(_("A reason is required to release a reservation."))
        snapshots = self.snapshot or {}
        for line in lines:
            expected = snapshots.get(str(line.id), line.quantity)
            if float_compare(
                line.quantity, expected, precision_rounding=line.product_uom_id.rounding
            ) != 0:
                raise UserError(_("A reservation changed after this confirmation opened. Refresh and retry."))
            if line.picked or line.state in ("done", "cancel"):
                raise UserError(_("Picked, done, or cancelled operations cannot be unreserved."))
        remaining = self.quantity_to_release or sum(lines.mapped("quantity_product_uom"))
        audits = []
        resolver = self.env["stock.reservation.source.service"]
        for line in lines:
            if remaining <= 0: break
            before = line.move_id.quantity
            release_product = min(remaining, line.quantity_product_uom)
            release_line = line.product_id.uom_id._compute_quantity(release_product, line.product_uom_id)
            move, picking, product = line.move_id, line.picking_id, line.product_id
            source = resolver.resolve(move)
            if float_compare(
                release_line, line.quantity, precision_rounding=line.product_uom_id.rounding
            ) == 0: line.unlink()
            else: line.quantity -= release_line
            after = move.quantity
            audits.append({"company_id": move.company_id.id, "action_type": "bulk_unreserve" if len(lines) > 1 else "unreserve",
                "product_id": product.id, "picking_id": picking.id, "move_id": move.id, "quantity_before": before,
                "quantity_changed": before - after, "quantity_after": after,
                "source_document_model": source["model"], "source_document_id": source["id"],
                "source_document_reference": source["reference"],
                "reason": dict(self._fields["reason"].selection).get(self.reason, _("Not specified")), "notes": self.notes})
            remaining -= release_product
        self.env["stock.reservation.audit"].create(audits)
        return {"type": "ir.actions.client", "tag": "soft_reload"}
