from odoo import api, models


class StockReservationControl(models.AbstractModel):
    _name = "stock.reservation.control"
    _description = "Stock Reservation Control Center API"

    @api.model
    def dashboard(self, filters=None, tab="product", offset=0, limit=80):
        return self.env["stock.reservation.service"].get_dashboard(filters or {}, tab, offset, min(limit, 200))

    @api.model
    def reservation_details(self, product_id, filters=None, offset=0, limit=80):
        return self.env["stock.reservation.service"].get_product_details(product_id, filters or {}, offset, min(limit, 200))

    @api.model
    def check_availability(self, move_id):
        return self.env["stock.reservation.service"].check_availability(move_id)
