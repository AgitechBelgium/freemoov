/** @odoo-module **/

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
            const response = await fetch('/web/dataset/call_kw/website/check_stock_availability', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        model: 'website',
                        method: 'check_stock_availability',
                        args: [[], combination.product_id],
                        kwargs: {},
                    },
                }),
            });
            const result = await response.json();
            if (result && result.result) {
                const data = result.result;
                combination.stock_availability = parseInt(data['qty_avail'] || 0);
                combination.is_dropship = parseInt(data['is_dropship'] || 0);
            }
        } catch (e) {
            console.warn("Error fetching stock availability:", e);
        }
    }
};
