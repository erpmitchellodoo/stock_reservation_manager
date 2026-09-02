from odoo.exceptions import AccessError
from .common import ReservationCase


class TestMultiCompany(ReservationCase):
    def test_unallowed_company_filter_rejected(self):
        other = self.env["res.company"].create({"name": "Other Reservation Company"})
        with self.assertRaises(AccessError):
            self.env["stock.reservation.control"].with_context(allowed_company_ids=[self.env.company.id]).dashboard({"company_ids": [other.id]}, "product", 0, 10)
