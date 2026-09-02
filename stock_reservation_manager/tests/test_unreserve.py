from .common import ReservationCase


class TestUnreserve(ReservationCase):
    def test_selective_unreserve_and_audit(self):
        move = self.make_move(40)
        move._action_assign()
        line = move.move_line_ids[:1]
        wizard = self.env["stock.reservation.unreserve.wizard"].create({"move_line_ids": [(6, 0, line.ids)],
            "quantity_to_release": 10, "reason": "manager", "snapshot": {str(line.id): line.quantity}})
        wizard.action_confirm()
        self.assertEqual(move.quantity, 30)
        audit = self.env["stock.reservation.audit"].search([("move_id", "=", move.id)])
        self.assertEqual(audit.quantity_changed, 10)

    def test_bulk_unreserve_and_optional_reason(self):
        first, second = self.make_move(10, "BULK-1"), self.make_move(15, "BULK-2")
        (first | second)._action_assign()
        lines = first.move_line_ids | second.move_line_ids
        self.env.company.reservation_require_unreserve_reason = False
        wizard = self.env["stock.reservation.unreserve.wizard"].create({
            "move_line_ids": [(6, 0, lines.ids)],
            "snapshot": {str(line.id): line.quantity for line in lines},
        })
        wizard.action_confirm()
        audits = self.env["stock.reservation.audit"].search([("move_id", "in", (first | second).ids)])
        self.assertEqual(len(audits), 2)
        self.assertEqual(set(audits.mapped("action_type")), {"bulk_unreserve"})
        self.assertEqual(set(audits.mapped("reason")), {"Not specified"})
