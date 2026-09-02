from odoo.exceptions import AccessError
from .common import ReservationCase


class TestSecurity(ReservationCase):
    def test_non_manager_cannot_unreserve(self):
        move = self.make_move(10)
        move._action_assign()
        user = self.env["res.users"].create({"name": "Reservation Viewer", "login": "reservation-viewer",
            "group_ids": [(6, 0, [self.env.ref("stock.group_stock_user").id])]})
        line = move.move_line_ids[:1]
        with self.assertRaises(AccessError):
            self.env["stock.reservation.unreserve.wizard"].with_user(user).create({"move_line_ids": [(6, 0, line.ids)], "reason": "manager"})

    def test_non_manager_cannot_check_availability(self):
        move = self.make_move(10)
        user = self.env["res.users"].create({"name": "Reservation Availability Viewer", "login": "reservation-availability-viewer",
            "group_ids": [(6, 0, [self.env.ref("stock.group_stock_user").id])]})
        with self.assertRaises(AccessError):
            self.env["stock.reservation.control"].with_user(user).check_availability(move.id)
