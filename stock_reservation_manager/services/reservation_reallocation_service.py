from odoo import api, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare


class ReservationReallocationService(models.AbstractModel):
    _name = "stock.reservation.reallocation.service"
    _description = "Native Reservation Reallocation Service"

    @api.model
    def _validate(self, line_ids, target_move_id, quantities, snapshots=None):
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(_("Only Reservation Control Managers can reallocate stock."))
        lines = self.env["stock.move.line"].browse(line_ids).exists()
        target = self.env["stock.move"].browse(target_move_id).exists()
        if not lines or not target or len(lines.company_id) != 1 or lines.company_id not in self.env.companies:
            raise AccessError(_("Reservations must belong to one authorized company."))
        if target.company_id != lines.company_id or target.product_id != lines.product_id:
            raise UserError(_("Source reservations and target demand must use the same company and product."))
        if not lines.company_id.reservation_reallocation_enabled:
            raise UserError(_("Reservation reallocation is disabled for this company."))
        for line in lines:
            quantity = float(quantities.get(str(line.id), 0))
            if quantity <= 0 or quantity > line.quantity_product_uom:
                raise UserError(_("The release quantity must be positive and cannot exceed the reservation."))
            if line.picked or line.state in ("done", "cancel"):
                raise UserError(_("Picked, done, or cancelled operations cannot be reallocated."))
            if snapshots is not None:
                expected = snapshots.get(str(line.id))
                if expected is None or float_compare(
                    line.quantity, expected, precision_rounding=line.product_uom_id.rounding
                ) != 0:
                    raise UserError(_("A reservation changed after the preview. Refresh and retry."))
        return lines, target

    @api.model
    def preview(self, line_ids, target_move_id, quantities):
        lines, target = self._validate(line_ids, target_move_id, quantities)
        released = sum(float(quantities[str(line.id)]) for line in lines)
        missing = max(target.product_uom_qty - target.quantity, 0)
        return {"guaranteed": False, "released": released, "target_before": target.quantity,
                "expected_target": min(released, missing),
                "message": _("Odoo will reassign using native reservation rules; a specific lot or quant is not guaranteed.")}

    @api.model
    def execute(self, line_ids, target_move_id, quantities, snapshots, reason, notes=False):
        lines, target = self._validate(line_ids, target_move_id, quantities, snapshots)
        if lines.company_id.reservation_require_reallocation_reason and not reason:
            raise UserError(_("A reason is required."))
        target_before = target.quantity
        audits = []
        resolver = self.env["stock.reservation.source.service"]
        for line in lines:
            source_move, source_picking, product = line.move_id, line.picking_id, line.product_id
            source_before = source_move.quantity
            source = resolver.resolve(source_move)
            release_product = float(quantities[str(line.id)])
            release_line = product.uom_id._compute_quantity(release_product, line.product_uom_id)
            if float_compare(
                release_line, line.quantity, precision_rounding=line.product_uom_id.rounding
            ) == 0:
                line.unlink()
            else:
                line.quantity -= release_line
            audits.append({"company_id": source_move.company_id.id, "action_type": "reallocate",
                           "product_id": product.id, "picking_id": source_picking.id,
                           "move_id": source_move.id, "target_move_id": target.id,
                           "quantity_before": source_before, "quantity_changed": source_before - source_move.quantity,
                           "quantity_after": source_move.quantity,
                           "source_document_model": source["model"], "source_document_id": source["id"],
                           "source_document_reference": source["reference"],
                           "reason": reason or _("Not specified"), "notes": notes})
        target._action_assign()
        for values in audits:
            values["result_notes"] = _("Target reservation changed from %(before)s to %(after)s.",
                                        before=target_before, after=target.quantity)
        self.env["stock.reservation.audit"].create(audits)
        return {"target_before": target_before, "target_after": target.quantity,
                "target_state": target.state, "released": sum(item["quantity_changed"] for item in audits)}
