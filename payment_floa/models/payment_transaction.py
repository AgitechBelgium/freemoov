# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

FLOA_PAYMENT_STATUS_MAPPING = {
    'Success': 'done',
    'pending': 'pending',
    'BankRefusal': 'cancel',
    'Refusal': 'cancel',
    'TechnicalError': 'error',
}


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    floa_deal_reference = fields.Char(
        string="FLOA Deal Reference",
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Overrides
    # -------------------------------------------------------------------------

    def _get_specific_rendering_values(self, processing_values):
        """Create FLOA deal + finalize → return redirect URL to payment page."""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'floa':
            return res

        provider = self.provider_id
        base_url = provider.get_base_url()
        amount_cents = int(round(self.amount * 100))

        # Build deal creation payload from partner data
        partner = self.partner_id
        deal_payload = self._floa_build_deal_payload(partner, amount_cents)

        # Step 1: Create deal with the CustomerInformationForm header so FLOA
        # collects any missing data (birth date, NRN, phone) on its own form.
        # Odoo-side data (items, history, address, email, civility, and any
        # optional fields already persisted on the partner) is still sent.
        try:
            deal_response = provider._floa_create_deal(
                deal_payload, use_customer_form=True,
            )
        except Exception as e:
            _logger.error("FLOA create deal failed: %s", e)
            raise ValidationError(
                _("FLOA: impossible de créer le dossier de paiement. %s") % str(e)
            )

        deal_reference = deal_response.get('dealReference')
        deal_status = deal_response.get('status')

        if deal_status == 'REJECTED':
            raise ValidationError(
                _("FLOA: le dossier a été refusé. Le paiement en 3x n'est pas disponible pour cette commande.")
            )

        self.floa_deal_reference = deal_reference
        _logger.info("FLOA deal created: %s (status: %s)", deal_reference, deal_status)

        # Step 2: Finalize deal
        finalize_payload = {
            'merchantReference': self.reference,
            'merchantFinancedAmount': amount_cents,
            'configuration': {
                'culture': 'fr-BE',
                'sessionModes': ['WebPage'],
                'backUrl': f'{base_url}/payment/floa/cancel?reference={self.reference}',
                'returnUrl': f'{base_url}/payment/floa/return',
                'notificationUrl': f'{base_url}/payment/floa/notification',
            },
        }

        try:
            finalize_response = provider._floa_finalize_deal(deal_reference, finalize_payload)
        except Exception as e:
            _logger.error("FLOA finalize deal failed: %s", e)
            raise ValidationError(
                _("FLOA: impossible de finaliser le dossier. %s") % str(e)
            )

        # Extract payment page URL from the finalize response.
        # Per FLOA spec the response contains a HAL-style "links" array with
        # entries shaped {href, rel, method}. The customer-facing redirect is
        # the link whose rel hints at the payment page; if FLOA stops tagging
        # rels we fall back to the first https URL.
        payment_url = None
        links = finalize_response.get('links') or []
        preferred_rels = ('paymentPage', 'payment-page', 'payment_page', 'self')
        for rel in preferred_rels:
            for link in links:
                if link.get('rel') == rel and link.get('href', '').startswith('https://'):
                    payment_url = link['href']
                    break
            if payment_url:
                break
        if not payment_url:
            for link in links:
                if link.get('href', '').startswith('https://'):
                    payment_url = link['href']
                    break

        if not payment_url:
            _logger.error("FLOA finalize returned no usable link: %s", finalize_response)
            raise ValidationError(
                _("FLOA: aucune URL de paiement reçue.")
            )

        _logger.info("FLOA payment URL obtained for deal %s", deal_reference)

        return {
            'api_url': payment_url,
            'reference': self.reference,
        }

    @api.model
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find the transaction from FLOA notification data."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'floa':
            return tx

        reference = notification_data.get('orderRef')
        if not reference:
            raise ValidationError(
                _("FLOA: notification reçue sans référence de commande (orderRef).")
            )

        tx = self.search([
            ('reference', '=', reference),
            ('provider_code', '=', 'floa'),
        ])
        if not tx:
            raise ValidationError(
                _("FLOA: aucune transaction trouvée pour la référence %s.") % reference
            )

        return tx

    def _process_notification_data(self, notification_data):
        """Process FLOA payment notification and update transaction status."""
        super()._process_notification_data(notification_data)
        if self.provider_code != 'floa':
            return

        # Verify HMAC
        if not self.provider_id._floa_verify_hmac(notification_data):
            _logger.warning(
                "FLOA: HMAC verification failed for tx %s", self.reference
            )
            raise ValidationError(
                _("FLOA: la signature HMAC est invalide.")
            )

        status = notification_data.get('status', '')
        complementary = notification_data.get('complementaryStatus', '')
        deal_ref = notification_data.get('dealRegistration', '')

        _logger.info(
            "FLOA notification for %s: status=%s, complementary=%s, deal=%s",
            self.reference, status, complementary, deal_ref,
        )

        if deal_ref:
            self.floa_deal_reference = deal_ref

        # Map FLOA status to Odoo transaction state
        mapped_status = FLOA_PAYMENT_STATUS_MAPPING.get(status, 'error')

        if mapped_status == 'done':
            self._set_done()
        elif mapped_status == 'pending':
            self._set_pending()
        elif mapped_status == 'cancel':
            self._set_canceled(
                state_message=_("FLOA: paiement refusé (%s)") % complementary
            )
        else:
            self._set_error(
                state_message=_("FLOA: erreur technique (%s — %s)") % (status, complementary)
            )

    # -------------------------------------------------------------------------
    # FLOA-specific helpers
    # -------------------------------------------------------------------------

    def _floa_build_deal_payload(self, partner, amount_cents):
        """Build the deal creation payload from the Odoo partner and order.

        Expects a complete partner profile (address + phone + birth date).
        Callers that want FLOA to collect missing data on their page must
        pass ``use_customer_form=True`` to ``_floa_create_deal``.
        """
        import re

        sale_order = self.sale_order_ids[:1] if self.sale_order_ids else None

        # --- Items -----------------------------------------------------
        items = []
        if sale_order:
            for line in sale_order.order_line.filtered(
                lambda l: not l.is_delivery and l.product_uom_qty > 0
            ):
                cat = self._floa_get_item_category(line.product_id)
                items.append({
                    'name': (line.product_id.name or 'Article')[:128],
                    'amount': int(round(line.price_total * 100)),
                    'quantity': int(line.product_uom_qty),
                    'reference': str(line.product_id.default_code or line.product_id.id),
                    'category': cat['category'],
                    'subCategory': cat['subCategory'],
                })

        if not items:
            items = [{
                'name': self.reference,
                'amount': amount_cents,
                'quantity': 1,
                'reference': self.reference,
                'category': 'Sport',
                'subCategory': 'Mobility',
            }]

        item_count = sum(item['quantity'] for item in items)

        # --- Civility --------------------------------------------------
        civility = 'Mr'
        if partner.title and partner.title.shortcut in ('Mme', 'Mrs.', 'Ms.'):
            civility = 'Mrs'

        # --- First / last name ----------------------------------------
        name_parts = (partner.name or 'Client').split(' ', 1)
        first_name = name_parts[0][:64]
        last_name = (name_parts[1] if len(name_parts) > 1 else first_name)[:64]

        # --- Address ---------------------------------------------------
        zip_code = (partner.zip or '').strip().replace(' ', '')
        home_address = {
            'line1': (partner.street or '')[:70],
            'zipCode': zip_code,
            'city': partner.city or '',
            'countryCode': 'BE',
        }
        if partner.street2:
            home_address['line2'] = partner.street2[:70]

        # --- Customer base --------------------------------------------
        customer = {
            'civility': civility,
            'firstName': first_name,
            'lastName': last_name,
            'email': partner.email or '',
            'nationality': 'BE',
            'homeAddress': home_address,
        }

        # --- Phone (optional here; FLOA collects it if invalid) -------
        # FLOA validates the BE numbering plan: mobiles must be +324XXXXXXXX.
        # We send the partner's mobile only if it normalizes to that pattern;
        # otherwise FLOA's customer form prompts for one.
        phone = self._floa_normalize_be_mobile(partner.mobile or partner.phone or '')
        if phone and re.match(r'^\+324\d{8}$', phone):
            customer['mobilePhoneNumber'] = phone

        # --- Birth date (mandatory) -----------------------------------
        if partner.floa_birth_date:
            customer['birthDate'] = partner.floa_birth_date.strftime('%Y-%m-%d')

        # --- Birth country (necessary) --------------------------------
        birth_country = partner.floa_birth_country_id
        customer['birthCountryCode'] = (birth_country.code if birth_country else 'BE')

        # --- Tax ID (national number) ---------------------------------
        national_number = partner._floa_get_national_number()
        if national_number:
            customer['taxIdNumber'] = national_number

        # --- Customer history (necessary) -----------------------------
        customer['history'] = self._floa_build_customer_history(partner)

        # --- Shipping address & method --------------------------------
        shipping_address = dict(home_address)  # same country / fields
        shipping_method = self._floa_get_shipping_method()

        payload = {
            'merchantReference': self.reference,
            'device': self._floa_get_device_type(),
            'shippingMethod': shipping_method,
            'merchantFinancedAmount': amount_cents,
            'itemCount': item_count,
            'items': items,
            'customers': [customer],
            'shippingAddress': shipping_address,
        }

        _logger.info("FLOA deal payload for %s: %s", self.reference, payload)
        return payload

    # ------------------------------------------------------------------
    # Payload helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _floa_normalize_be_mobile(raw):
        """Normalize a phone string to the Belgian E.164 mobile format.

        Accepts any usual input (``0470…``, ``+32 470…``, ``0032470…``,
        ``32470…`` or just ``470…``) and returns ``+324XXXXXXXX`` when
        possible, otherwise an empty string.
        """
        import re
        if not raw:
            return ''
        p = re.sub(r'[\s.\-/()]', '', raw)
        if not p:
            return ''
        if p.startswith('+'):
            return p
        if p.startswith('00'):
            return '+' + p[2:]
        if p.startswith('32'):
            return '+' + p
        if p.startswith('0'):
            return '+32' + p[1:]
        return '+32' + p

    def _floa_get_device_type(self):
        """Return the FLOA ``device`` value based on the current user agent."""
        try:
            from odoo.http import request
            ua = (request.httprequest.user_agent.string or '').lower() if request else ''
        except Exception:  # pylint: disable=broad-except
            ua = ''
        if not ua:
            return 'Desktop'
        if 'ipad' in ua:
            return 'Ipad'
        if 'iphone' in ua or 'ipod' in ua:
            return 'IPhone'
        if 'android' in ua:
            return 'AndroidTablet' if 'tablet' in ua else 'AndroidSmartPhone'
        if 'mobile' in ua:
            return 'SmartPhone'
        if 'tablet' in ua:
            return 'Tablet'
        return 'Desktop'

    def _floa_get_shipping_method(self):
        """Map the order's carrier (if any) to a FLOA shipping method code."""
        self.ensure_one()
        sale_order = self.sale_order_ids[:1] if self.sale_order_ids else None
        if not sale_order or not sale_order.carrier_id:
            return 'STD'
        name = (sale_order.carrier_id.name or '').lower()
        if 'relay' in name or 'relais' in name or 'point' in name:
            return 'REL'
        if 'chrono' in name:
            return 'CHR'
        if 'express' in name or 'expr' in name:
            return 'EXP'
        if 'click' in name or 'magasin' in name or 'collect' in name:
            return 'COL'
        if 'ups' in name:
            return 'UPS'
        return 'STD'

    def _floa_get_item_category(self, product):
        """Map an Odoo product to a FLOA category / subCategory pair.

        FLOA's category list is free-form in the public schema; we send the
        product's public category when available, falling back to Sport/Mobility
        which matches Freemoov's catalog (trottinettes / vélos / gyroroues).
        """
        default = {'category': 'Sport', 'subCategory': 'Mobility'}
        if not product or not product.public_categ_ids:
            return default
        leaf = product.public_categ_ids[0]
        root = leaf
        while root.parent_id:
            root = root.parent_id
        return {
            'category': (root.name or default['category'])[:64],
            'subCategory': (leaf.name or default['subCategory'])[:64],
        }

    def _floa_build_customer_history(self, partner):
        """Return the FLOA customer history block.

        Fields follow FLOA's schema: customers[].history.{firstOrderDate,
        lastOrderDate, validatedOrderCount, validatedOrderAmount,
        canceledOrderCount, createdDate}. The current in-progress order is
        excluded so counts reflect past activity only.
        """
        SaleOrder = self.env['sale.order'].sudo()
        domain_base = [('partner_id', '=', partner.id)]
        if self.sale_order_ids:
            domain_base.append(('id', 'not in', self.sale_order_ids.ids))

        validated = SaleOrder.search(
            domain_base + [('state', 'in', ('sale', 'done'))],
            order='date_order asc',
        )
        canceled_count = SaleOrder.search_count(
            domain_base + [('state', '=', 'cancel')]
        )

        def _fmt(dt):
            return dt.strftime('%Y-%m-%dT%H:%M:%S') if dt else ''

        history = {
            'createdDate': _fmt(partner.create_date),
            'validatedOrderCount': len(validated),
            'validatedOrderAmount': int(round(sum(validated.mapped('amount_total')) * 100)),
            'canceledOrderCount': canceled_count,
        }
        if validated:
            history['firstOrderDate'] = _fmt(validated[0].date_order)
            history['lastOrderDate'] = _fmt(validated[-1].date_order)
        return history
