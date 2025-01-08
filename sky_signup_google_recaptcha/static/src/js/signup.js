odoo.define('sky_signup_google_recaptcha.signup_inherit', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');
    var SignUpForm = publicWidget.registry.SignUpForm;
    const { ReCaptcha } = require('google_recaptcha.ReCaptchaV3');

    SignUpForm.include({
        init: function () {
            this._super.apply(this, arguments); // Call the original init method
            this._recaptcha = new ReCaptcha();
        },

        willStart: async function () {
            await this._super.apply(this, arguments); // Call the original willStart method
            await this._recaptcha.loadLibs(); // Ensure ReCaptcha libraries are loaded
        },

        _onSubmit: async function (ev) {
            ev.preventDefault();
            this._super.apply(this, arguments);

            const tokenObj = await this._recaptcha.getToken("oe_signup_form");
            const recaptchaInput = document.createElement("input");

            recaptchaInput.type = "hidden";
            recaptchaInput.name = "recaptcha_token_response";
            recaptchaInput.value = tokenObj.token;

            this.el.appendChild(recaptchaInput);
            this.el.submit();
        },
    });
});