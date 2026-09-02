/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ReservationManager extends Component {
    static template = "stock_reservation_manager.ReservationManager";
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            tab: "product",
            search: "",
            data: { kpis: {}, rows: [] },
            detail: null,
            selectedLineIds: [],
            offset: 0,
        });
        this.tabs = [
            ["product", "By Product"], ["transaction", "By Transaction"], ["customer", "By Customer"],
            ["warehouse", "By Warehouse"], ["aging", "Aging"], ["partial", "Partial Reservations"],
            ["unreserved", "Unreserved Demand"], ["conflict", "Conflicts"],
        ];
        this.tabHelp = {
            product: {
                title: "Reservations by product",
                description: "See which products have stock reserved, how much remains free, and which products need attention. Click a product to inspect its reservation lines.",
            },
            transaction: {
                title: "Reservations by transaction",
                description: "Review reservation progress for each transfer or stock demand. Use Check Availability to ask Odoo to reserve currently available stock.",
            },
            customer: {
                title: "Reservations by customer",
                description: "Understand how much stock is committed to each customer and how many products and transfers are affected.",
            },
            warehouse: {
                title: "Reservations by warehouse",
                description: "Compare on-hand, reserved, and free stock across warehouses to identify locations with high reservation pressure.",
            },
            aging: {
                title: "Reservation aging",
                description: "Find reservations that have remained active for a long time. Age is estimated from the operational move-line date.",
            },
            partial: {
                title: "Partially reserved demand",
                description: "Shows demand where only part of the requested quantity is reserved, so you can focus on orders that are not ready in full.",
            },
            unreserved: {
                title: "Unreserved demand",
                description: "Shows confirmed demand with no reserved stock. Use Check Availability after stock becomes available or priorities change.",
            },
            conflict: {
                title: "Reservation conflicts",
                description: "Highlights products where competing demand is greater than available stock. Review priorities before unreserving or reallocating stock.",
            },
        };
        onWillStart(() => this.load());
    }
    get filters() { return { search: this.state.search }; }
    get activeTabHelp() { return this.tabHelp[this.state.tab]; }
    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("stock.reservation.control", "dashboard", [this.filters, this.state.tab, this.state.offset, 80]);
        } finally { this.state.loading = false; }
    }
    async selectTab(tab) { this.state.tab = tab; this.state.offset = 0; this.state.detail = null; await this.load(); }
    async search(ev) { this.state.search = ev.target.value; if (!ev.key || ev.key === "Enter") await this.load(); }
    async openDetail(row) {
        if (!row.product_id) return;
        this.state.selectedLineIds = [];
        this.state.detail = await this.orm.call(
            "stock.reservation.control", "reservation_details", [row.product_id, this.filters, 0, 80]
        );
    }
    openRecord(model, id) { if (model && id) this.action.doAction({ type: "ir.actions.act_window", res_model: model, res_id: id, views: [[false, "form"]] }); }
    isLineSelected(lineId) { return this.state.selectedLineIds.includes(lineId); }
    toggleLine(lineId) {
        this.state.selectedLineIds = this.isLineSelected(lineId)
            ? this.state.selectedLineIds.filter((id) => id !== lineId)
            : [...this.state.selectedLineIds, lineId];
    }
    toggleAllLines() {
        const lineIds = this.state.detail?.lines.map((line) => line.id) || [];
        this.state.selectedLineIds = this.state.selectedLineIds.length === lineIds.length ? [] : lineIds;
    }
    get selectedLines() {
        return (this.state.detail?.lines || []).filter((line) => this.isLineSelected(line.id));
    }
    async reloadAfterAction(productId) {
        await this.load();
        if (productId) {
            await this.openDetail({ product_id: productId });
        }
    }
    async openUnreserve() {
        const lines = this.selectedLines;
        if (!lines.length) {
            this.notification.add("Select at least one reservation line.", { type: "warning" });
            return;
        }
        const productId = this.state.detail.product_id;
        const snapshot = Object.fromEntries(lines.map((line) => [String(line.id), line.line_quantity]));
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: lines.length > 1 ? "Bulk Unreserve" : "Unreserve",
            res_model: "stock.reservation.unreserve.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_move_line_ids: [[6, 0, lines.map((line) => line.id)]],
                default_quantity_to_release: lines.length === 1 ? lines[0].reserved : 0,
                default_snapshot: snapshot,
            },
        }, { onClose: () => this.reloadAfterAction(productId) });
    }
    async openReallocation() {
        const lines = this.selectedLines;
        if (lines.length !== 1) {
            this.notification.add("Select exactly one reservation line to reallocate.", { type: "warning" });
            return;
        }
        const line = lines[0];
        const productId = this.state.detail.product_id;
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Reallocate Reservation",
            res_model: "stock.reservation.reallocation.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_source_line_ids: [[6, 0, [line.id]]],
                default_quantity_to_release: line.reserved,
                default_snapshot: { [String(line.id)]: line.line_quantity },
            },
        }, { onClose: () => this.reloadAfterAction(productId) });
    }
    async checkAvailability(moveId) {
        const result = await this.orm.call("stock.reservation.control", "check_availability", [moveId]);
        this.notification.add(`Reservation updated: ${result.reserved}`, { type: "success" }); await this.load();
    }
}
registry.category("actions").add("stock_reservation_manager.ReservationManager", ReservationManager);
