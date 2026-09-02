from .common import ReservationCase


class TestReallocation(ReservationCase):
    def test_preview_and_native_sequence(self):
        source, target = self.make_move(100, "SOURCE"), self.make_move(50, "TARGET")
        source._action_assign()
        line = source.move_line_ids[:1]
        service = self.env["stock.reservation.reallocation.service"]
        preview = service.preview(line.ids, target.id, {str(line.id): 50})
        self.assertFalse(preview["guaranteed"])
        self.assertEqual(preview["expected_target"], 50)
        result = service.execute(line.ids, target.id, {str(line.id): 50}, {str(line.id): line.quantity}, "Urgent demand")
        self.assertEqual(result["target_after"], 50)

    def test_changed_snapshot_is_rejected(self):
        source, target = self.make_move(20), self.make_move(20)
        source._action_assign()
        line = source.move_line_ids[:1]
        with self.assertRaises(Exception):
            self.env["stock.reservation.reallocation.service"].execute(line.ids, target.id, {str(line.id): 5}, {str(line.id): 999}, "Test")
