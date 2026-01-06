# Copyright © 2024 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License OPL-1 (https://www.odoo.com/documentation/15.0/legal/licenses.html).

from typing import Dict, List

from odoo import api, fields, models
from odoo.http import request
from odoo.tools.json import scriptsafe as json_scriptsafe


class Website(models.Model):
    _inherit = "website"

    cookies_consent_manager = fields.Selection(
        selection=[('none', 'None'), ('odoo', 'Odoo Cookie Bar')],
        default='none',
        required=True,
    )
    cookies_consent_is_logged = fields.Boolean(
        string='Debug Logging',
        help='Log tracking events to a browser console.',
    )

    @api.model
    def _get_cookie_consents(self) -> Dict[str, bool]:
        """ Get and return the cookie "website_cookies_bar" dict value.
            Method to use with the Odoo Cookies Bar.
            Data sample: {'required': True, 'optional': False, 'functional': True, 'marketing': False}
        """
        cookie_types = json_scriptsafe.loads(
            request.httprequest.cookies.get('website_cookies_bar', '{}')
        )
        # Got from "addons/website/models/ir_http.py" to handle previous cookies values
        # pre-16.0 compatibility, `website_cookies_bar` was `"true"`.
        # In that case we delete that cookie and let the user choose again.
        if not isinstance(cookie_types, dict):
            request.future_response.set_cookie('website_cookies_bar', expires=0, max_age=0)
            return {}

        return cookie_types

    def _cookies_optional_is_granted(self) -> bool:
        """ Indicate a visitor consent for the "optional" cookies. """
        self.ensure_one()
        return self._get_cookie_consents().get('optional', False) \
            if self.cookies_consent_manager == 'odoo' else self.cookies_consent_manager == 'none'

    def _cookies_functional_is_granted(self) -> bool:
        self.ensure_one()
        return self._cookies_optional_is_granted()

    def _cookies_analytics_is_granted(self) -> bool:
        self.ensure_one()
        return self._cookies_optional_is_granted()

    def _cookies_marketing_is_granted(self) -> bool:
        self.ensure_one()
        return self._cookies_optional_is_granted()

    @api.model
    def _cookies_fields_to_invalidate_cache(self) -> List[str]:
        """ Determine fields of the "website" model on changing which webpages should be updated. """
        return ['cookies_consent_manager']

    def write(self, vals):
        # Handle the Odoo Cookies Bar state
        if 'cookies_consent_manager' in vals:
            vals['cookies_bar'] = vals.get('cookies_consent_manager') == 'odoo'
        elif 'cookies_bar' in vals:
            vals['cookies_consent_manager'] = 'odoo' if vals.get('cookies_bar') else 'none'
        result = super(Website, self).write(vals)
        # Invalidate the caches to apply changes on webpages.
        if any(fld in vals for fld in self._cookies_fields_to_invalidate_cache()):
            self.env['ir.qweb'].clear_caches()
        return result
