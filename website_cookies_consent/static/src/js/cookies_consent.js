odoo.define('website_cookies_consent.cookies_consent', function (require) {
    "use strict";

    const publicWidget = require('web.public.widget');

    publicWidget.registry.cookies_consent = publicWidget.Widget.extend({

        _getCookieConsentManager: function() {
            return document.querySelector('body').getAttribute('data-cookies-consent-manager');
        },

        _isCookieConsentLogged: function() {
            return document.querySelector('body').getAttribute('data-cookies-consent-debug-logging');
        },

        _updateCookieConsent: function() {
            if (this._isCookieConsentLogged()) { console.log(`[Cookie Consent | Base] _updateCookieConsent`) }
        },

    });

    return publicWidget.registry.cookies_consent;
});
