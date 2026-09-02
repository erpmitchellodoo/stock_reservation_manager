# Stock Reservation Manager & Control Center

Operational visibility and permission-controlled management of Odoo 19's native stock reservations. The module never stores a parallel stock balance and never writes `stock.quant` quantities directly.

## Odoo 19 reservation model

Active reservations are unpicked `stock.move.line` records with positive `quantity` / stored `quantity_product_uom`. Their lot, package, owner and source location identify the reserved quant dimensions. Quant `reserved_quantity` is maintained by Odoo's move-line ORM hooks. `stock.move.quantity` is the normalized reserved/processed move quantity used by assignment state computation.

Assignment uses `stock.move._action_assign()` (or `stock.picking.action_assign()`). Whole-move release uses `stock.move._do_unreserve()`. This add-on performs selective release by changing/unlinking eligible unpicked move lines through ORM, which invokes Odoo's native quant synchronization.

`stock.move.line.date` is only an operational proxy for reservation age and may be refreshed when quantity or picked state changes. The dashboard explicitly labels age as estimated.

## Safety

- Native access rules and allowed-company context are retained; reservation mutations do not use `sudo()`.
- State and quantity snapshots are checked immediately before mutations.
- Audit rows are immutable and record only manual actions initiated here.
- Reallocation is release followed by native `_action_assign()` and reports the actual result; it does not promise a particular quant or lot.

## Display defaults

The control center always opens on the **By Product** view. Reservation details always display the lot/serial field, using `-` when a reservation has no assigned lot or serial number.

## Manager workflow

Inventory Managers can run controlled reservation actions directly from the control center:

1. Use **By Transaction**, **Partial Reservations**, or **Unreserved Demand** and click **Check Availability** to run Odoo's native assignment logic for that move.
2. Open a product detail panel and select one or more active reservation lines.
3. Use **Unreserve** for one line or **Bulk Unreserve** for multiple lines. The wizard supports a partial quantity and records the configured reason and notes.
4. Select exactly one line and choose **Reallocate**. Select an active target move for the same product and company, preview the expected impact, and confirm.
5. Review the automatically created immutable entry under **Reservation Audit History**.

Reasons are enforced only when the corresponding company setting is enabled. All operations re-check permissions, company, state, and quantity snapshots immediately before changing reservations.
