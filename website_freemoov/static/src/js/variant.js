/** @odoo-module **/

import VariantMixin from "website_sale_stock.VariantMixin";
import "website_sale.website_sale";
import { qweb as QWeb } from "web.core";
const {Markup} = require('web.utils');
var rpc = require('web.rpc');

const oldChangeCombinationStock = VariantMixin._onChangeCombinationStock;
/**
 * Displays additional info messages regarding the product's
 * stock and the wishlist.
 *
 * @override
 */
VariantMixin._onChangeCombinationStock = function (ev, $parent, combination) {
    oldChangeCombinationStock.apply(this, arguments);
    const messageEl = this.el.querySelector('div.availability_messages');
        if (messageEl) {
            combination.stock_availability = 0
            rpc.query({
                model: 'website',
                method: 'check_stock_availability',
                args: [[],combination.product_id],
            }).then(function (data) {
                console.log("data ==== ",data)
                combination.stock_availability = parseInt(data['qty_avail']);
                combination.is_dropship = parseInt(data['is_dropship']);
                messageEl.insertAdjacentHTML('afterbegin',
                    QWeb.render('website_freemoov.product_availability', combination)
                );
            });
        }
};
