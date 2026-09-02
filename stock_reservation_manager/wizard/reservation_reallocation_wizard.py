from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ReservationReallocationWizard(models.TransientModel):
    _name = "stock.reservation.reallocation.wizard"
    _description = "Reservation Reallocation Preview"

    source_line_ids = fields.Many2many("stock.move.line", required=True)
    target_move_id = fields.Many2one("stock.move", required=True)
    quantity_to_release = fields.Float(required=True, digits="Product Unit")
    reason = fields.Char()
    notes = fields.Text()
    preview_data = fields.Json(readonly=True)
    snapshot = fields.Json(readonly=True)
    source_product_id = fields.Many2one("product.product", compute="_compute_source_context")
    company_id = fields.Many2one("res.company", compute="_compute_source_context")
    reason_required = fields.Boolean(compute="_compute_source_context")

    @api.depends("source_line_ids")
    def _compute_source_context(self):
        for wizard in self:
            wizard.source_product_id = wizard.source_line_ids.product_id if len(wizard.source_line_ids.product_id) == 1 else False
            wizard.company_id = wizard.source_line_ids.company_id if len(wizard.source_line_ids.company_id) == 1 else False
            wizard.reason_required = bool(wizard.company_id.reservation_require_reallocation_reason)

    def action_preview(self):
        self.ensure_one()
        if len(self.source_line_ids) != 1:
            raise UserError(_("This V1 wizard accepts one source reservation per preview."))
        quantities = {str(self.source_line_ids.id): self.quantity_to_release}
        self.preview_data = self.env["stock.reservation.reallocation.service"].preview(self.source_line_ids.ids, self.target_move_id.id, quantities)
        self.snapshot = {str(self.source_line_ids.id): self.source_line_ids.quantity}
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}

    def action_confirm(self):
        self.ensure_one()
        if not self.preview_data:
            raise UserError(_("Preview the impact before confirming."))
        return self.env["stock.reservation.reallocation.service"].execute(self.source_line_ids.ids, self.target_move_id.id,
            {str(self.source_line_ids.id): self.quantity_to_release}, self.snapshot, self.reason or False, self.notes)
