from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    reservation_aging_enabled = fields.Boolean(default=True)
    reservation_old_days = fields.Integer(default=8)
    reservation_aging_buckets = fields.Char(default="1,3,7,15,30")
    reservation_conflict_enabled = fields.Boolean(default=True)
    reservation_unreserve_enabled = fields.Boolean(default=True)
    reservation_reallocation_enabled = fields.Boolean(default=True)
    reservation_require_unreserve_reason = fields.Boolean(default=True)
    reservation_require_reallocation_reason = fields.Boolean(default=True)
    reservation_critical_percent = fields.Float(default=90.0)
