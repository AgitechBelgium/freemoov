/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.websiteSaleDelivery.include({
    async _handleCarrierUpdateResult(carrierInput) {
        const result = await this.rpc('/shop/update_carrier', {
            'carrier_id': carrierInput.value,
            'no_reset_access_point_address': this.forceClickCarrier,
        });
        this.result = result;
        this._handleCarrierUpdateResultBadge(result);
        if (!carrierInput.checked) {
            return;
        }
        const setHtml = (sel, value) => {
            const el = document.querySelector(sel);
            if (el) el.innerHTML = value;
        };
        setHtml('#order_delivery .monetary_field', result.new_amount_delivery);
        setHtml('#order_total_untaxed .monetary_field', result.new_amount_untaxed);
        setHtml('#order_total_taxes .monetary_field', result.new_amount_tax);
        document.querySelectorAll('#order_total .monetary_field, #amount_total_summary.monetary_field')
            .forEach((el) => { el.innerHTML = result.new_amount_total; });
        if (result.new_amount_total_raw !== undefined) {
            this._updateShippingCost(result.new_amount_total_raw);
            const hasPaymentMethod = document.querySelector("div[name='o_website_sale_free_cart']") === null;
            const shouldDisplayPaymentMethod = result.new_amount_total_raw !== 0;
            if (hasPaymentMethod !== shouldDisplayPaymentMethod) {
                location.reload(false);
            }
        }
    },
});
