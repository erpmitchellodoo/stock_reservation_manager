from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    reservation_aging_enabled = fields.Boolean(related="company_id.reservation_aging_enabled", readonly=False)
    reservation_old_days = fields.Integer(related="company_id.reservation_old_days", readonly=False)
    reservation_aging_buckets = fields.Char(related="company_id.reservation_aging_buckets", readonly=False)
    reservation_conflict_enabled = fields.Boolean(related="company_id.reservation_conflict_enabled", readonly=False)
    reservation_unreserve_enabled = fields.Boolean(related="company_id.reservation_unreserve_enabled", readonly=False)
    reservation_reallocation_enabled = fields.Boolean(related="company_id.reservation_reallocation_enabled", readonly=False)
    reservation_require_unreserve_reason = fields.Boolean(related="company_id.reservation_require_unreserve_reason", readonly=False)
    reservation_require_reallocation_reason = fields.Boolean(related="company_id.reservation_require_reallocation_reason", readonly=False)
    reservation_critical_percent = fields.Float(related="company_id.reservation_critical_percent", readonly=False)
