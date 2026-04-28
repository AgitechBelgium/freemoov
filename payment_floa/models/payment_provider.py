# -*- coding: utf-8 -*-

import hashlib
import hmac
import json
import logging
import time

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# FLOA API URLs
FLOA_API_URLS = {
    'test': 'https://api.floapay.io/api-nx-live-int',
    'enabled': 'https://api.floapay.io/api-nx-prd-live',
}

# FLOA Widget URLs
FLOA_WIDGET_URLS = {
    'test': 'https://prp-widget.floa.com/floa-widget.js',
    'enabled': 'https://widget.floa.com/floa-widget.js',
}

# Product codes available for Belgium
FLOA_PRODUCT_CODES_BE = [
    ('BC3XFBE', 'Belgique 3X Gratuit (sans frais client)'),
    ('BC3XCBE', 'Belgique 3X (frais partagés)'),
]


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('floa', "FLOA Pay")],
        ondelete={'floa': 'set default'},
    )
    floa_client_id = fields.Char(
        string="FLOA Client ID",
        groups='base.group_system',
    )
    floa_client_secret = fields.Char(
        string="FLOA Client Secret",
        groups='base.group_system',
    )
    floa_hmac_key = fields.Char(
        string="FLOA HMAC Key",
        groups='base.group_system',
    )
    floa_product_code = fields.Selection(
        selection=FLOA_PRODUCT_CODES_BE,
        string="FLOA Product",
        default='BC3XFBE',
    )

    # -------------------------------------------------------------------------
    # Overrides
    # -------------------------------------------------------------------------

    def _get_supported_currencies(self):
        supported = super()._get_supported_currencies()
        if self.code == 'floa':
            return supported.filtered(lambda c: c.name == 'EUR')
        return supported

    @api.model
    def _get_compatible_providers(self, *args, **kwargs):
        """Hide FLOA when the customer is not Belgian or amount is out of range.

        The mandatory customer fields (birth date, phone, NRN) are collected
        via the inline form displayed under the FLOA radio button, so missing
        fields alone do not hide the provider here.
        """
        providers = super()._get_compatible_providers(*args, **kwargs)

        partner_id = args[1] if len(args) > 1 else kwargs.get('partner_id')
        amount = args[2] if len(args) > 2 else kwargs.get('amount')

        floa_providers = providers.filtered(lambda p: p.code == 'floa')
        if not floa_providers:
            return providers

        remove_floa = False

        if partner_id:
            partner = self.env['res.partner'].browse(partner_id)
            if partner.country_id and partner.country_id.code != 'BE':
                remove_floa = True

        if amount is not None and (amount < 50 or amount > 6000):
            remove_floa = True

        if remove_floa:
            providers -= floa_providers

        return providers

    # -------------------------------------------------------------------------
    # FLOA API helpers
    # -------------------------------------------------------------------------

    def _floa_get_api_url(self):
        """Return the FLOA API base URL based on provider state."""
        self.ensure_one()
        return FLOA_API_URLS.get(self.state, FLOA_API_URLS['test'])

    def _floa_get_widget_url(self):
        """Return the FLOA widget JS URL based on provider state."""
        self.ensure_one()
        return FLOA_WIDGET_URLS.get(self.state, FLOA_WIDGET_URLS['test'])

    def _floa_is_production(self):
        """Return whether the provider is in production mode."""
        self.ensure_one()
        return self.state == 'enabled'

    # In-process cache: {(provider_id, state): (token, expires_at_epoch)}
    # FLOA tokens are valid 3600s; we keep a 60s safety margin so the
    # second hop of a checkout (create deal -> finalize) reuses one token.
    _FLOA_TOKEN_CACHE = {}
    _FLOA_TOKEN_SAFETY_MARGIN = 60

    def _floa_get_access_token(self):
        """Obtain an OAuth2 access token from FLOA.

        Returns the access_token string. Tokens are cached in-process for
        their advertised lifetime minus a small safety margin so a single
        checkout (create deal + finalize) does not trigger two OAuth round
        trips. Raises if the request fails.
        """
        self.ensure_one()
        cache_key = (self.id, self.state)
        cached = self._FLOA_TOKEN_CACHE.get(cache_key)
        if cached and cached[1] > time.time():
            return cached[0]

        base_url = self._floa_get_api_url()
        url = f"{base_url}/oauth/token?grant_type=client_credentials"

        import base64
        credentials = base64.b64encode(
            f"{self.floa_client_id}:{self.floa_client_secret}".encode()
        ).decode()

        headers = {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            'Authorization': f'Basic {credentials}',
        }

        response = requests.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        token = data['access_token']
        expires_in = int(data.get('expires_in') or 3600)
        expires_at = time.time() + max(expires_in - self._FLOA_TOKEN_SAFETY_MARGIN, 60)
        self._FLOA_TOKEN_CACHE[cache_key] = (token, expires_at)

        _logger.info("FLOA OAuth token obtained, expires in %s seconds", expires_in)
        return token

    def _floa_invalidate_token_cache(self):
        """Drop the cached OAuth token for this provider.

        Call this after a 401 from the FLOA API to force a fresh token on the
        next request.
        """
        self.ensure_one()
        self._FLOA_TOKEN_CACHE.pop((self.id, self.state), None)

    def _floa_make_request(self, method, endpoint, payload=None, params=None, extra_headers=None):
        """Make an authenticated request to the FLOA API.

        On a 401 the cached token is invalidated and the request is retried
        once with a fresh token, to recover from a token expiring mid-flight
        (the in-process cache cannot see clock drift on the FLOA side).

        :param str method: HTTP method (GET, POST)
        :param str endpoint: API endpoint path (e.g., '/api/v1/deals')
        :param dict payload: JSON body for POST requests
        :param dict params: Query parameters
        :param dict extra_headers: Additional headers to include
        :returns: Response JSON
        :rtype: dict
        """
        self.ensure_one()
        base_url = self._floa_get_api_url()
        url = f"{base_url}{endpoint}"

        for attempt in range(2):
            token = self._floa_get_access_token()
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
            }
            if extra_headers:
                headers.update(extra_headers)

            _logger.info("FLOA API %s %s params=%s", method, url, params)
            response = requests.request(
                method, url, headers=headers,
                json=payload, params=params, timeout=30,
            )

            if response.status_code == 401 and attempt == 0:
                _logger.warning("FLOA API 401, invalidating token and retrying")
                self._floa_invalidate_token_cache()
                continue

            if response.status_code not in (200, 201):
                _logger.error(
                    "FLOA API error %s: %s", response.status_code, response.text
                )
            response.raise_for_status()
            return response.json()

    def _floa_create_deal(self, values, use_customer_form=False):
        """Create a FLOA deal (step 1).

        The checkout collects every mandatory field (birth date, phone, NRN)
        before this call, so the deal is created without the
        ``Implementation-Type: CustomerInformationForm`` header — FLOA only
        asks the customer for card details on their page.

        Passing ``use_customer_form=True`` falls back to the legacy behavior
        where FLOA collects missing fields itself. Only meant as a safety net
        (e.g. manual back-office operations where the partner profile is
        incomplete).

        :param dict values: Deal data (merchantReference, amount, customer, items, etc.)
        :param bool use_customer_form: Enable the CustomerInformationForm fallback.
        :returns: Deal response with dealReference and status
        :rtype: dict
        """
        self.ensure_one()
        extra_headers = None
        if use_customer_form:
            extra_headers = {'Implementation-Type': 'CustomerInformationForm'}
        return self._floa_make_request(
            'POST', '/api/v1/deals',
            payload=values,
            params={'productCode': self.floa_product_code},
            extra_headers=extra_headers,
        )

    def _floa_finalize_deal(self, deal_reference, values):
        """Finalize a FLOA deal (step 2) — generates payment page URL.

        :param str deal_reference: FLOA deal reference (e.g., FIN10027179040)
        :param dict values: Finalization data (URLs, culture, amounts)
        :returns: Finalization response with payment page link
        :rtype: dict
        """
        self.ensure_one()
        return self._floa_make_request(
            'POST', f'/api/v1/deals/{deal_reference}/finalize',
            payload=values,
        )

    def _floa_simulate_installments(self, amount_cents):
        """Simulate installment plans for display purposes.

        :param int amount_cents: Amount in cents
        :returns: Simulated installment plans
        :rtype: dict
        """
        self.ensure_one()
        return self._floa_make_request(
            'GET', '/api/v1/simulated-installment-plans',
            params={
                'merchantFinancedAmount': amount_cents,
                'productCodes': self.floa_product_code,
                'countryCode': 'BE',
            },
        )

    def _floa_get_installment_plan(self, deal_reference):
        """Get the installment plan status for a deal.

        :param str deal_reference: FLOA deal reference
        :returns: Installment plan details
        :rtype: dict
        """
        self.ensure_one()
        return self._floa_make_request(
            'GET', f'/api/v1/deals/{deal_reference}/installment-plan',
        )

    @staticmethod
    def _floa_calculate_hmac(notification_data, hmac_key):
        """Calculate HMAC-SHA1 signature for notification verification.

        The concatenation order is:
        Status * ComplementaryStatus * OrderRef * DealRegistration *
        Amount * DecimalPosition * Currency * Date * FreeText *

        :param dict notification_data: Notification payload from FLOA
        :param str hmac_key: Merchant HMAC secret key
        :returns: Calculated HMAC hex digest
        :rtype: str
        """
        fields_order = [
            'status', 'complementaryStatus', 'orderRef', 'dealRegistration',
            'amount', 'decimalPosition', 'currency', 'date', 'freeText',
        ]
        concatenated = '*'.join(
            str(notification_data.get(f, '')) for f in fields_order
        ) + '*'

        return hmac.new(
            hmac_key.encode('utf-8'),
            concatenated.encode('utf-8'),
            hashlib.sha1,
        ).hexdigest()

    def _floa_verify_hmac(self, notification_data):
        """Verify the HMAC signature of a FLOA notification.

        :param dict notification_data: Notification payload
        :returns: True if HMAC is valid
        :rtype: bool
        """
        self.ensure_one()
        received_hmac = notification_data.get('hmac', '')
        calculated_hmac = self._floa_calculate_hmac(
            notification_data, self.floa_hmac_key
        )
        return hmac.compare_digest(received_hmac.lower(), calculated_hmac.lower())
