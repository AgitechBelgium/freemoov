# -*- encoding: utf-8 -*-
#########################################################################################
#
#    Copyright (C) 2019 Skyscend Business Solutions (https://www.skyscendbs.com)
#    Copyright (C) 2020 Skyscend Business Solutions  Pvt. Ltd.(<https://skyscendbs.com>)
#
#########################################################################################

from odoo import http, _
from odoo.http import request
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.exceptions import ValidationError, UserError


class InheritedAuthSignupHome(AuthSignupHome):
    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        qcontext = {k: v for (k, v) in request.params.items()}
        qcontext["error"] = False

        if request.httprequest.method == 'POST':
            error = False
            if request.env.company.enable_recaptcha_validation:
                try:
                    res = request.env['ir.http']._verify_request_recaptcha_token('oe_signup_form')
                    if not res:
                        error = _("Suspicious activity detected by Google reCAPTCHA.")
                except (ValidationError, UserError) as e:
                    error = e.args[0]
            if error:
                sign_context = self.get_auth_signup_qcontext()
                sign_context["error"] = error
                response = request.render('auth_signup.signup', sign_context)

                response.headers['X-Frame-Options'] = 'SAMEORIGIN'
                response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
                return response
        return super().web_auth_signup(*args, **kw)
