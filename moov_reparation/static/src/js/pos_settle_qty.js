/** @odoo-module */

import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    setQuantityFromSOL(saleOrderLine) {
        this.set_quantity(saleOrderLine.qty_to_invoice);
    },
});
