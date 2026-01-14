/** @odoo-module **/

import { renderToElement } from "@web/core/utils/render";
import { rpc } from "@web/core/network/rpc";
import VariantMixin from "@website_sale_stock/js/variant_mixin";

const oldChangeCombinationStock = VariantMixin._onChangeCombinationStock;

/**
 * Displays additional info messages regarding the product's
 * stock and the wishlist.
 *
 * @override
 */
VariantMixin._onChangeCombinationStock = async function (ev, $parent, combination) {
    oldChangeCombinationStock.apply(this, arguments);
    const messageEl = this.el ? this.el.querySelector('div.availability_messages') : null;
    if (messageEl) {
        combination.stock_availability = 0;
        try {
            const data = await rpc('/web/dataset/call_kw/website/check_stock_availability', {
                model: 'website',
                method: 'check_stock_availability',
                args: [[], combination.product_id],
                kwargs: {},
            });
            console.log("data ==== ", data);
            combination.stock_availability = parseInt(data['qty_avail']);
            combination.is_dropship = parseInt(data['is_dropship']);
            const html = renderToElement('website_freemoov.product_availability', combination);
            messageEl.insertAdjacentElement('afterbegin', html);
        } catch (e) {
            console.warn("Error fetching stock availability:", e);
        }
    }
};
