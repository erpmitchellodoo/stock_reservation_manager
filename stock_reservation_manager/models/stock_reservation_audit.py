from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class StockReservationAudit(models.Model):
    _name = "stock.reservation.audit"
    _description = "Manual Stock Reservation Control Audit"
    _order = "date desc, id desc"
    _check_company_auto = True

    date = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True, index=True)
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    company_id = fields.Many2one("res.company", required=True, readonly=True, index=True)
    action_type = fields.Selection([
        ("unreserve", "Unreserve"), ("bulk_unreserve", "Bulk Unreserve"),
        ("reallocate", "Reallocate"), ("check_availability", "Check Availability"),
    ], required=True, readonly=True, index=True)
    product_id = fields.Many2one("product.product", required=True, readonly=True, check_company=True, index=True)
    picking_id = fields.Many2one("stock.picking", readonly=True, check_company=True, index=True)
    move_id = fields.Many2one("stock.move", readonly=True, check_company=True, index=True)
    source_document_model = fields.Char(readonly=True)
    source_document_id = fields.Integer(readonly=True)
    source_document_reference = fields.Char(readonly=True)
    quantity_before = fields.Float(readonly=True, digits="Product Unit")
    quantity_changed = fields.Float(readonly=True, digits="Product Unit")
    quantity_after = fields.Float(readonly=True, digits="Product Unit")
    target_move_id = fields.Many2one("stock.move", readonly=True, check_company=True)
    reason = fields.Char(required=True, readonly=True)
    notes = fields.Text(readonly=True)
    result_notes = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(_("Only Reservation Control Managers can create audit entries."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Reservation audit entries are immutable."))

    def unlink(self):
        raise AccessError(_("Reservation audit entries are immutable."))
