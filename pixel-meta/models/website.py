from odoo import api, fields, models


class Website(models.Model):
    _inherit = 'website'

    facebook_pixel_key = fields.Char('Facebook Pixel ID')
    fbp_cookies_consent_is_revoked = fields.Boolean(
        string='Cookie Consent is Revoked',
        help='The cookie consent for Facebook tracking is revoked by default for new visitors to the website.',
        default=False,
    )

    def _fbp_params(self):
        self.ensure_one()
        return [
            # Add the Consent directive for the current website
            {
                'action': 'consent',
                # Consent may be granted if a visitor allows the optional cookies,
                # or the visitor's consent depends on the default FB consent state and
                # if the visitor does not have the Odoo's "website_cookies_bar" cookie.
                'key': 'grant'
                if self._cookies_optional_is_granted()
                or not self.fbp_cookies_consent_is_revoked and 'required' not in self._get_cookie_consents()
                else 'revoke',
                'extra_vals': {},
            },
            # Add the Init directive
            {
                'action': 'init',
                'key': self.facebook_pixel_key or '',
                'extra_vals': {},
            },
        ]

    def fbp_get_primary_key(self):
        self.ensure_one()
        return self.facebook_pixel_key or ''

    @api.model
    def _cookies_fields_to_invalidate_cache(self):
        field_list = super(Website, self)._cookies_fields_to_invalidate_cache()
        field_list.append('fbp_cookies_consent_is_revoked')
        return field_list
