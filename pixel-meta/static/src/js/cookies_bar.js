odoo.define('website_facebook_pixel.cookies_bar', function (require) {
    "use strict";

    const publicWidget = require('web.public.widget');
    const CookiesConsentWidget = require('website_cookies_consent.cookies_consent');

    publicWidget.registry.cookies_bar_facebook_consent = CookiesConsentWidget.extend({
        selector: '#website_cookies_bar',
        events: {
            'click #cookies-consent-essential': '_onAcceptRequiredCookies',
            'click #cookies-consent-all': '_onAcceptOptionalCookies',
        },

        /**
        * @private
        * @param ev
        */
        _onAcceptRequiredCookies(ev) {
            // Click on Essential Cookies Only
            if (ev.target.id === 'cookies-consent-essential') {
                if (this._isCookieConsentLogged()) { console.log(`[Cookie Consent | Facebook] - Revoke`) }
                const websiteFbq = window.fbq || function () {};
                websiteFbq.call(this, 'consent', 'revoke');
            }
        },
        /**
        * @private
        * @param ev
        */
        _onAcceptOptionalCookies(ev) {
            // Click on All Cookies
            if (ev.target.id === 'cookies-consent-all') {
                if (this._isCookieConsentLogged()) { console.log(`[Cookie Consent | Facebook] - Grant`) }
                const websiteFbq = window.fbq || function () {};
                websiteFbq.call(this, 'consent', 'grant');
            }
        },
    });

    return publicWidget.registry.cookies_bar_facebook_consent;
});
