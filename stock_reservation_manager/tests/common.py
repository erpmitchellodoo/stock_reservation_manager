from odoo.tests.common import TransactionCase


class ReservationCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager_group = cls.env.ref("stock.group_stock_manager")
        cls.env.user.groups_id += cls.manager_group
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.env.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.customer = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create({
            "name": "Reservation Test Product",
            "detailed_type": "product",
        })
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.stock, 100)

    def make_move(self, quantity, origin="SRM-TEST"):
        move = self.env["stock.move"].create({"name": self.product.display_name,
            "reference": origin, "product_id": self.product.id,
            "product_uom_qty": quantity, "product_uom": self.product.uom_id.id,
            "location_id": self.stock.id, "location_dest_id": self.customer.id,
            "origin": origin, "company_id": self.env.company.id})
        move._action_confirm()
        return move
