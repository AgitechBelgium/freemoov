/** @odoo-module **/

import VariantMixin from "website_sale.VariantMixin";

/*
 * FLOA Pay Widget — dynamic initialization & variant-price sync.
 *
 * Loads the external FLOA widget script on-demand and initializes
 * the installment simulation wherever [data-floa-offers] appears
 * (product page, cart sidebar).
 *
 * On variant change the widget is reinitialized with the new price.
 */

// -------------------------------------------------------------------------
// Configuration
// -------------------------------------------------------------------------

var FLOA_CONFIG = {
    widgetUrl: 'https://prp-widget.floa.com/floa-widget.js',  // preprod
    offers: ['BC3XFBE'],
    country: 'BE',
    locale: 'fr',
    theme: 'brand',
    pnf: 'https://www.floapay.be/CGV-belgium',
    production: false,
    minAmount: 5000,   // 50 € in cents
    maxAmount: 600000, // 6 000 € in cents
};

// -------------------------------------------------------------------------
// Script loader
// -------------------------------------------------------------------------

var _floaLoaded = false;
var _floaLoadPromise = null;

function _loadFloaScript() {
    if (_floaLoaded) {
        return Promise.resolve();
    }
    if (_floaLoadPromise) {
        return _floaLoadPromise;
    }
    _floaLoadPromise = new Promise(function (resolve, reject) {
        var script = document.createElement('script');
        script.type = 'module';
        script.src = FLOA_CONFIG.widgetUrl;
        script.onload = function () {
            _floaLoaded = true;
            resolve();
        };
        script.onerror = function () {
            console.warn('[FLOA] Failed to load widget script');
            reject();
        };
        document.head.appendChild(script);
    });
    return _floaLoadPromise;
}

// -------------------------------------------------------------------------
// Widget initialization
// -------------------------------------------------------------------------

function _initFloaWidget(amountCents) {
    if (!amountCents || amountCents < FLOA_CONFIG.minAmount || amountCents > FLOA_CONFIG.maxAmount) {
        return;
    }

    var config = {
        offers: FLOA_CONFIG.offers,
        theme: FLOA_CONFIG.theme,
        amount: amountCents,
        locale: FLOA_CONFIG.locale,
        country: FLOA_CONFIG.country,
        pnf: FLOA_CONFIG.pnf,
        production: FLOA_CONFIG.production,
    };

    // Cleanup previous instance before reinitializing
    if (window.cleanupFloaWidget) {
        try { window.cleanupFloaWidget(); } catch (e) { /* ignore */ }
    }

    if (window.initFloaWidget) {
        window.initFloaWidget(config);
    }
}

/**
 * Read the initial amount from the data attribute set by the QWeb template,
 * load the FLOA script, and initialize the widget.
 */
function _initFromDataAttribute() {
    var containers = document.querySelectorAll('[data-floa-offers]');
    if (!containers.length) {
        return;
    }

    // Use the first container's data-floa-amount as the initial price
    var amount = 0;
    for (var i = 0; i < containers.length; i++) {
        var attr = containers[i].getAttribute('data-floa-amount');
        if (attr) {
            amount = parseInt(attr, 10);
            break;
        }
    }

    if (amount) {
        _loadFloaScript().then(function () {
            // Small delay to let the FLOA script register window.initFloaWidget
            setTimeout(function () {
                _initFloaWidget(amount);
            }, 200);
        });
    }
}

// -------------------------------------------------------------------------
// Hook into Odoo variant changes (product page)
// -------------------------------------------------------------------------

var _origOnChangeCombination = VariantMixin._onChangeCombination;

VariantMixin._onChangeCombination = function (ev, $parent, combination) {
    _origOnChangeCombination.apply(this, arguments);

    if (!combination || !combination.price) {
        return;
    }

    var amountCents = Math.round(combination.price * 100);

    // Update data attribute for potential re-reads
    var containers = document.querySelectorAll('.floa-widget-product[data-floa-offers]');
    for (var i = 0; i < containers.length; i++) {
        containers[i].setAttribute('data-floa-amount', amountCents);
    }

    _loadFloaScript().then(function () {
        setTimeout(function () {
            _initFloaWidget(amountCents);
        }, 100);
    });
};

// -------------------------------------------------------------------------
// Initial load
// -------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', _initFromDataAttribute);
