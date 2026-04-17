# -*- coding: utf-8 -*-

import json
import logging
import pprint
import re
from datetime import date, datetime

from odoo import _, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class FloaController(http.Controller):
    _return_url = '/payment/floa/return'
    _notification_url = '/payment/floa/notification'
    _cancel_url = '/payment/floa/cancel'
    _save_customer_info_url = '/shop/floa/save_customer_info'

    # ------------------------------------------------------------------
    # Checkout — inline form data collection
    # ------------------------------------------------------------------

    @http.route(
        _save_customer_info_url,
        type='json', auth='public', website=True, csrf=True,
    )
    def floa_save_customer_info(self, birth_date=None, national_number=None,
                                birth_country_code=None, mobile_phone=None,
                                **kwargs):
        """Pre-save FLOA-specific customer data on the partner before payment.

        Called by the inline form JS right before the transaction is created,
        so that `_floa_build_deal_payload` can read the values from the
        partner without any race condition.
        """
        order = request.website.sale_get_order()
        if not order or not order.partner_id:
            return {'error': _("Aucun panier actif.")}

        partner = order.partner_id
        public_partner = request.env.ref('base.public_partner', raise_if_not_found=False)
        if public_partner and partner == public_partner:
            return {'error': _("Veuillez vous connecter ou compléter votre adresse.")}

        values = {}

        # Birth date — mandatory
        if not birth_date:
            return {'error': _("La date de naissance est requise.")}
        try:
            parsed = datetime.strptime(birth_date, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return {'error': _("Format de date de naissance invalide (attendu : AAAA-MM-JJ).")}
        today = date.today()
        if parsed >= today:
            return {'error': _("La date de naissance doit être dans le passé.")}
        age = (today - parsed).days // 365
        if age < 18:
            return {'error': _("Le paiement FLOA est réservé aux personnes majeures.")}
        if age > 120:
            return {'error': _("Date de naissance invalide.")}
        values['floa_birth_date'] = parsed

        # National number — optional but recommended (11 digits)
        if national_number:
            cleaned = re.sub(r'[\s.\-/]', '', national_number)
            if not re.match(r'^\d{11}$', cleaned):
                return {'error': _("Le numéro national doit contenir 11 chiffres.")}
            values['floa_national_number'] = cleaned

        # Birth country — optional, defaults to BE on the partner if empty
        if birth_country_code:
            country = request.env['res.country'].sudo().search(
                [('code', '=', birth_country_code.upper())], limit=1,
            )
            if country:
                values['floa_birth_country_id'] = country.id

        # Mobile phone — if provided, update the partner so it flows into the deal
        if mobile_phone:
            digits = re.sub(r'[\s.\-/()]', '', mobile_phone)
            if digits.startswith('00'):
                digits = '+' + digits[2:]
            elif digits.startswith('0'):
                digits = '+32' + digits[1:]
            elif not digits.startswith('+'):
                digits = '+32' + digits
            if not re.match(r'^\+324\d{8}$', digits):
                return {'error': _("Numéro de téléphone mobile belge invalide.")}
            values['mobile'] = digits

        partner.sudo().write(values)
        _logger.info(
            "FLOA customer info saved on partner %s for order %s: %s",
            partner.id, order.name, list(values.keys()),
        )
        return {'success': True}

    @http.route(_return_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def floa_return(self, **post):
        """Handle customer redirect from FLOA after payment.

        FLOA sends a POST with form-urlencoded data containing:
        status, complementaryStatus, dealRegistration, orderRef,
        amount, decimalPosition, currency, date, hmac, freeText
        """
        req = request.httprequest
        _logger.info(
            "FLOA RETURN — full dump:\n"
            "  URL: %s\n"
            "  method: %s\n"
            "  headers: %s\n"
            "  query string: %s\n"
            "  raw body: %s\n"
            "  parsed form: %s\n"
            "  user-agent: %s",
            req.url, req.method, dict(req.headers), req.query_string,
            (req.get_data(cache=True) or b'')[:2000], pprint.pformat(post),
            req.user_agent.string if req.user_agent else '',
        )
        request.env['payment.transaction'].sudo()._handle_notification_data('floa', post)
        return request.redirect('/payment/status')

    @http.route(_notification_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def floa_notification(self, **post):
        """Handle server-to-server webhook from FLOA.

        FLOA sends a single POST with JSON body after payment resolution.
        This is the authoritative notification — the return URL is just for UX.
        """
        raw = request.httprequest.get_data(cache=True) or b''
        try:
            data = json.loads(raw or b'{}')
        except (json.JSONDecodeError, TypeError):
            data = post

        _logger.info(
            "FLOA NOTIFICATION — full dump:\n"
            "  URL: %s\n"
            "  headers: %s\n"
            "  raw body: %s\n"
            "  parsed: %s",
            request.httprequest.url, dict(request.httprequest.headers),
            raw[:2000], pprint.pformat(data),
        )
        request.env['payment.transaction'].sudo()._handle_notification_data('floa', data)
        return 'OK'

    @http.route(_cancel_url, type='http', auth='public', methods=['GET'], csrf=False)
    def floa_cancel(self, **params):
        """Handle customer cancellation (backUrl) from FLOA payment page."""
        reference = params.get('reference')
        _logger.info("FLOA cancel for reference: %s", reference)
        if reference:
            tx = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference),
                ('provider_code', '=', 'floa'),
            ], limit=1)
            if tx:
                tx._set_canceled(state_message="Paiement annulé par le client.")
        return request.redirect('/shop/cart')
