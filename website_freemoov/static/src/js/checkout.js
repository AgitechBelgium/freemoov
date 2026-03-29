odoo.define('website_freemoov.checkout', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');

    // ============================================
    // Toggle cart summary on mobile
    // ============================================
    publicWidget.registry.FmToggleSummary = publicWidget.Widget.extend({
        selector: '.toggle_summary',
        events: {
            'click': '_onToggle',
        },
        _onToggle: function (ev) {
            ev.preventDefault();
            var $target = this.$el.closest('.card-body').find('.toggle_summary_div');
            if ($target.hasClass('fm-open')) {
                $target.removeClass('fm-open').slideUp(250);
            } else {
                $target.addClass('fm-open').slideDown(250, function () {
                    // After animation, force flex display for ordering
                    $(this).css('display', 'flex');
                });
            }
            this.$el.toggleClass('active');
        },
    });

    // ============================================
    // Delivery carrier — visual feedback
    // ============================================
    publicWidget.registry.FmDeliverySelect = publicWidget.Widget.extend({
        selector: '#delivery_method',
        events: {
            'change input[name="delivery_type"]': '_onSelect',
        },
        start: function () {
            this._super.apply(this, arguments);
            this._highlightSelected();
        },
        _onSelect: function () {
            this._highlightSelected();
        },
        _highlightSelected: function () {
            this.$('.list-group-item').removeClass('fm-selected');
            this.$('input[name="delivery_type"]:checked')
                .closest('.list-group-item')
                .addClass('fm-selected');
        },
    });

    // ============================================
    // Payment method — visual feedback
    // ============================================
    publicWidget.registry.FmPaymentSelect = publicWidget.Widget.extend({
        selector: '.o_payment_form',
        events: {
            'change input[name="o_payment_radio"]': '_onSelect',
        },
        start: function () {
            this._super.apply(this, arguments);
            this._highlightSelected();
        },
        _onSelect: function () {
            this._highlightSelected();
        },
        _highlightSelected: function () {
            this.$('.o_payment_option_card').removeClass('fm-selected');
            this.$('input[name="o_payment_radio"]:checked')
                .closest('.o_payment_option_card')
                .addClass('fm-selected');
        },
    });

    // ============================================
    // Cart item removal animation
    // ============================================
    publicWidget.registry.FmCartRemove = publicWidget.Widget.extend({
        selector: '.fm-cart-lines',
        events: {
            'click .js_delete_product': '_onDelete',
        },
        _onDelete: function (ev) {
            var $item = $(ev.currentTarget).closest('.fm-cart-item');
            $item.addClass('fm-removing');
        },
    });

    // ============================================
    // Cart quantity — loading + price flash
    // ============================================
    publicWidget.registry.FmCartQuantity = publicWidget.Widget.extend({
        selector: '.fm-cart-lines',
        events: {
            'click .js_add_cart_json': '_onQtyChange',
        },
        _onQtyChange: function (ev) {
            var $item = $(ev.currentTarget).closest('.fm-cart-item');
            var $qtyGroup = $item.find('.css_quantity');
            var $price = $item.find('.fm-ci-price-amount');

            $qtyGroup.addClass('fm-loading');

            setTimeout(function () {
                $qtyGroup.removeClass('fm-loading');
                $price.addClass('fm-price-updated');
                setTimeout(function () {
                    $price.removeClass('fm-price-updated');
                }, 500);
            }, 800);
        },
    });

});
