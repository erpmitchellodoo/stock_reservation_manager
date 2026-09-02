from .common import ReservationCase


class TestReservationDashboard(ReservationCase):
    def test_native_reservation_aggregation_and_free_quantity(self):
        first, second = self.make_move(40, "SO001"), self.make_move(30, "SO002")
        (first | second)._action_assign()
        self.assertEqual(first.quantity, 40)
        dashboard = self.env["stock.reservation.control"].dashboard({}, "product", 0, 80)
        row = next(row for row in dashboard["rows"] if row["id"] == self.product.id)
        self.assertEqual(row["reserved"], 70)
        self.assertEqual(row["free"], 30)
        self.assertEqual(row["reservation_count"], 2)

    def test_partial_and_unreserved_demand(self):
        self.make_move(80)._action_assign()
        partial = self.make_move(50)
        partial._action_assign()
        empty = self.make_move(10)
        self.assertEqual(partial.state, "partially_available")
        self.assertEqual(empty.quantity, 0)
        self.assertTrue(self.env["stock.reservation.control"].dashboard({}, "partial", 0, 80)["rows"])
        self.assertTrue(self.env["stock.reservation.control"].dashboard({}, "unreserved", 0, 80)["rows"])

    def test_done_and_cancelled_excluded(self):
        move = self.make_move(10)
        move._action_cancel()
        rows = self.env["stock.reservation.control"].dashboard({}, "transaction", 0, 80)["rows"]
        self.assertNotIn(move.id, [row["id"] for row in rows])

    def test_product_detail_exposes_action_context(self):
        move = self.make_move(10)
        move._action_assign()
        details = self.env["stock.reservation.control"].reservation_details(self.product.id, {}, 0, 80)
        self.assertEqual(details["product_id"], self.product.id)
        self.assertEqual(details["lines"][0]["move_id"], move.id)
        self.assertEqual(details["lines"][0]["line_quantity"], move.move_line_ids[0].quantity)
