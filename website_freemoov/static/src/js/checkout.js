/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.FmToggleSummary = publicWidget.Widget.extend({
    selector: '.toggle_summary',
    events: {
        'click': '_onToggle',
    },

    _onToggle: function (ev) {
        ev.preventDefault();
        var $target = this.$el.closest('.card-body').find('.toggle_summary_div');
        $target.slideToggle(250);
        this.$el.toggleClass('active');
    },
});

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

publicWidget.registry.FmStepper = publicWidget.Widget.extend({
    selector: '.fm-stepper',

    start: function () {
        this._super.apply(this, arguments);
        this.$('.fm-stepper__step').each(function (index) {
            var $step = $(this);
            setTimeout(function () {
                $step.css({
                    'opacity': '1',
                    'transform': 'translateY(0)',
                });
            }, 100 + (index * 80));
        });
    },
});

publicWidget.registry.FmConfirmation = publicWidget.Widget.extend({
    selector: '.fm-confirmation__hero',

    start: function () {
        this._super.apply(this, arguments);
        var $steps = this.$el.siblings('.fm-confirmation__timeline')
            .find('.fm-timeline-step');
        $steps.each(function (index) {
            var $step = $(this);
            setTimeout(function () {
                $step.css({
                    'opacity': '1',
                    'transform': 'translateY(0)',
                });
            }, 400 + (index * 150));
        });
    },
});
