/** @odoo-module **/

// Odoo 17 module path. The legacy "website_sale.VariantMixin" alias was
// removed during the v16 -> v17 module path migration; using it makes the
// whole bundle fail to load with "module not defined" and the widget never
// initializes, so the data-floa-* container stays visually empty.
import VariantMixin from "@website_sale/js/sale_variant_mixin";

/*
 * FLOA Pay Widget — dynamic initialization & variant-price sync.
 *
 * Loads the external FLOA widget script on-demand and initializes
 * the installment simulation wherever [data-floa-offers] appears.
 *
 * Per-provider config (widget URL, production flag, offer code) is read
 * from data-* attributes set by the QWeb template, so the same JS bundle
 * works for sandbox and production providers without a rebuild.
 */

var FLOA_DEFAULTS = {
    widgetUrl: 'https://prp-widget.floa.com/floa-widget.js',
    offers: ['BC3XFBE'],
    country: 'BE',
    locale: 'fr',
    theme: 'brand',
    pnf: 'https://www.floapay.be/CGV-belgium',
    production: false,
    minAmount: 5000,
    maxAmount: 600000,
};

var _runtimeConfig = null;
var _floaLoaded = false;
var _floaLoadPromise = null;

function _readContainerConfig(container) {
    if (!container) {
        return null;
    }
    var widgetUrl = container.getAttribute('data-floa-widget-url') || FLOA_DEFAULTS.widgetUrl;
    var production = container.getAttribute('data-floa-production') === 'true';
    var productCode = container.getAttribute('data-floa-product-code') || FLOA_DEFAULTS.offers[0];
    return {
        widgetUrl: widgetUrl,
        offers: [productCode],
        production: production,
        country: FLOA_DEFAULTS.country,
        locale: FLOA_DEFAULTS.locale,
        theme: FLOA_DEFAULTS.theme,
        pnf: FLOA_DEFAULTS.pnf,
        minAmount: FLOA_DEFAULTS.minAmount,
        maxAmount: FLOA_DEFAULTS.maxAmount,
    };
}

function _loadFloaScript(widgetUrl) {
    if (_floaLoaded) {
        return Promise.resolve();
    }
    if (_floaLoadPromise) {
        return _floaLoadPromise;
    }
    _floaLoadPromise = new Promise(function (resolve, reject) {
        var script = document.createElement('script');
        script.type = 'module';
        script.src = widgetUrl;
        script.onload = function () {
            _floaLoaded = true;
            resolve();
        };
        script.onerror = function () {
            console.warn('[FLOA] Failed to load widget script from', widgetUrl);
            reject();
        };
        document.head.appendChild(script);
    });
    return _floaLoadPromise;
}

function _initFloaWidget(amountCents) {
    if (!_runtimeConfig) {
        return;
    }
    if (!amountCents || amountCents < _runtimeConfig.minAmount || amountCents > _runtimeConfig.maxAmount) {
        return;
    }

    var config = {
        offers: _runtimeConfig.offers,
        theme: _runtimeConfig.theme,
        amount: amountCents,
        locale: _runtimeConfig.locale,
        country: _runtimeConfig.country,
        pnf: _runtimeConfig.pnf,
        production: _runtimeConfig.production,
    };

    if (window.cleanupFloaWidget) {
        try { window.cleanupFloaWidget(); } catch (e) { /* ignore */ }
    }

    if (window.initFloaWidget) {
        window.initFloaWidget(config);
    }
}

function _initFromDataAttribute() {
    var container = document.querySelector('[data-floa-offers]');
    if (!container) {
        return;
    }

    _runtimeConfig = _readContainerConfig(container);

    var amount = parseInt(container.getAttribute('data-floa-amount') || '0', 10);
    if (!amount) {
        return;
    }

    _loadFloaScript(_runtimeConfig.widgetUrl).then(function () {
        setTimeout(function () {
            _initFloaWidget(amount);
        }, 200);
    });
}

var _origOnChangeCombination = VariantMixin._onChangeCombination;

VariantMixin._onChangeCombination = function (ev, $parent, combination) {
    _origOnChangeCombination.apply(this, arguments);

    if (!combination || !combination.price) {
        return;
    }

    var amountCents = Math.round(combination.price * 100);

    var containers = document.querySelectorAll('.floa-widget-product[data-floa-offers]');
    for (var i = 0; i < containers.length; i++) {
        containers[i].setAttribute('data-floa-amount', amountCents);
    }

    if (!_runtimeConfig && containers.length) {
        _runtimeConfig = _readContainerConfig(containers[0]);
    }
    if (!_runtimeConfig) {
        return;
    }

    _loadFloaScript(_runtimeConfig.widgetUrl).then(function () {
        setTimeout(function () {
            _initFloaWidget(amountCents);
        }, 100);
    });
};

document.addEventListener('DOMContentLoaded', _initFromDataAttribute);
