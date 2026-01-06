/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

// Get the base cookies_consent widget if available
const CookiesConsentWidget = publicWidget.registry.cookies_consent || publicWidget.Widget;

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
            if (this._isCookieConsentLogged && this._isCookieConsentLogged()) { 
                console.log(`[Cookie Consent | Facebook] - Revoke`);
            }
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
            if (this._isCookieConsentLogged && this._isCookieConsentLogged()) { 
                console.log(`[Cookie Consent | Facebook] - Grant`);
            }
            const websiteFbq = window.fbq || function () {};
            websiteFbq.call(this, 'consent', 'grant');
        }
    },
});

export default publicWidget.registry.cookies_bar_facebook_consent;
