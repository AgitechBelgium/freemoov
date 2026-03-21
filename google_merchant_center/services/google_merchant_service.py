# -*- coding: utf-8 -*-
# Enzo Nauté — 2026
"""
Client Google Merchant API : insert/delete produits.
Subprocess en Docker (contournement conflit OpenSSL), in-process sur Odoo.sh.
"""
import json
import logging
import os
import subprocess
import time

_logger = logging.getLogger(__name__)

GMC_LIBS_PATH = '/opt/odoo-gmc-libs'


def _script_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'gmc_api_runner.py')


def _use_subprocess():
    return os.path.isdir(GMC_LIBS_PATH) and os.path.isfile(_script_path())


def _get_client(credentials_json):
    """Build ProductInputsServiceClient from service account JSON dict."""
    from google.shopping import merchant_products_v1
    return merchant_products_v1.ProductInputsServiceClient.from_service_account_info(
        credentials_json
    )


def _build_product_input(product_data):
    """Build ProductInput and ProductAttributes from product_data dict."""
    from google.shopping import merchant_products_v1
    from google.shopping.merchant_products_v1 import Availability, Condition
    from google.shopping.type import Price

    attrs = merchant_products_v1.ProductAttributes()
    attrs.title = (product_data.get('title') or '')[:150]
    attrs.description = (product_data.get('description') or '')[:5000]
    attrs.link = product_data.get('link') or ''
    attrs.image_link = product_data.get('image_link') or ''
    if product_data.get('additional_image_links'):
        attrs.additional_image_links.extend(product_data['additional_image_links'][:10])

    availability = product_data.get('availability', 'IN_STOCK').upper()
    avail_map = {
        'OUT_OF_STOCK': Availability.OUT_OF_STOCK,
        'PREORDER': Availability.PREORDER,
        'BACKORDER': Availability.BACKORDER,
        'LIMITED_AVAILABILITY': Availability.LIMITED_AVAILABILITY,
    }
    attrs.availability = avail_map.get(availability, Availability.IN_STOCK)

    condition = (product_data.get('condition') or 'new').lower()
    cond_map = {'used': Condition.USED, 'refurbished': Condition.REFURBISHED}
    attrs.condition = cond_map.get(condition, Condition.NEW)

    # Price (required)
    price = Price()
    price.amount_micros = int(product_data.get('price_micros', 0))
    price.currency_code = product_data.get('currency_code', 'EUR')
    attrs.price = price

    # Sale price
    if product_data.get('sale_price_micros'):
        sale_price = Price()
        sale_price.amount_micros = int(product_data['sale_price_micros'])
        sale_price.currency_code = product_data.get('currency_code', 'EUR')
        attrs.sale_price = sale_price

    # Google product category
    if product_data.get('google_product_category'):
        attrs.google_product_category = str(product_data['google_product_category'])[:750]

    # Product type hierarchy
    if product_data.get('product_type'):
        attrs.product_types.append(str(product_data['product_type'])[:750])

    # Identifiers
    if product_data.get('gtin'):
        attrs.gtins.append(str(product_data['gtin']))
    if product_data.get('mpn'):
        attrs.mpn = product_data['mpn'][:70]
    if product_data.get('brand'):
        attrs.brand = product_data['brand'][:70]

    identifier_exists = product_data.get('identifier_exists', True)
    if not identifier_exists:
        attrs.identifier_exists = False

    # Shipping weight
    if product_data.get('shipping_weight_value') and product_data['shipping_weight_value'] > 0:
        from google.shopping.merchant_products_v1 import ShippingWeight
        sw = ShippingWeight()
        sw.value = float(product_data['shipping_weight_value'])
        sw.unit = product_data.get('shipping_weight_unit', 'kg')
        attrs.shipping_weight = sw

    # Shipping rates per country
    if product_data.get('shipping'):
        from google.shopping.merchant_products_v1 import Shipping
        for ship_data in product_data['shipping']:
            ship = Shipping()
            ship.country = ship_data.get('country', 'BE')
            ship_price = Price()
            ship_price.amount_micros = int(ship_data.get('price_micros', 0))
            ship_price.currency_code = ship_data.get('currency_code', 'EUR')
            ship.price = ship_price
            attrs.shipping.append(ship)

    # Free shipping threshold
    if product_data.get('free_shipping_threshold'):
        from google.shopping.merchant_products_v1 import FreeShippingThreshold
        for country in ('BE', 'FR', 'LU', 'NL'):
            threshold = FreeShippingThreshold()
            threshold.country = country
            threshold_price = Price()
            threshold_price.amount_micros = int(product_data['free_shipping_threshold'] * 1_000_000)
            threshold_price.currency_code = 'EUR'
            threshold.price_threshold = threshold_price
            attrs.free_shipping_threshold.append(threshold)

    # Ships from country
    if product_data.get('ships_from_country'):
        attrs.ships_from_country = product_data['ships_from_country']

    # Custom labels 0-4
    for i in range(5):
        key = 'custom_label_%d' % i
        val = product_data.get(key)
        if val:
            setattr(attrs, key, str(val)[:100])

    product_input = merchant_products_v1.ProductInput()
    product_input.offer_id = str(product_data.get('offer_id', ''))[:50]
    product_input.content_language = product_data.get('content_language', 'fr')
    product_input.feed_label = product_data.get('feed_label', 'BE')
    product_input.product_attributes = attrs
    return product_input


class GoogleMerchantService(object):
    """Sync products with Google Merchant Center via Merchant API."""

    def __init__(self, merchant_id, data_source_id, credentials_json):
        self.merchant_id = str(merchant_id)
        self.data_source_id = str(data_source_id)
        self.credentials_json = credentials_json
        self._client = None

    def _get_client(self):
        if self._client is None and self.credentials_json:
            self._client = _get_client(self.credentials_json)
        return self._client

    @property
    def parent(self):
        return 'accounts/%s' % self.merchant_id

    @property
    def data_source(self):
        return 'accounts/%s/dataSources/%s' % (self.merchant_id, self.data_source_id)

    def insert_product(self, product_data):
        """
        Insert or update (upsert) a product.
        Returns (success: bool, response_or_error_message).
        """
        if not self.credentials_json:
            return False, 'No credentials configured'
        if _use_subprocess():
            return self._insert_via_subprocess(product_data)
        client = self._get_client()
        if not client:
            return False, 'No credentials configured'
        try:
            product_input = _build_product_input(product_data)
            from google.shopping import merchant_products_v1
            request = merchant_products_v1.InsertProductInputRequest(
                parent=self.parent,
                product_input=product_input,
                data_source=self.data_source,
            )
            response = client.insert_product_input(request=request)
            return True, response
        except Exception as e:
            _logger.warning('GMC insert_product failed: %s', e)
            return False, str(e)

    def _insert_via_subprocess(self, product_data):
        payload = {
            'action': 'insert',
            'merchant_id': self.merchant_id,
            'data_source_id': self.data_source_id,
            'credentials_json': self.credentials_json,
            'product_data': product_data,
        }
        try:
            env = os.environ.copy()
            env['PYTHONPATH'] = GMC_LIBS_PATH
            proc = subprocess.Popen(
                ['python3', _script_path()],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=os.path.dirname(_script_path()),
            )
            out, err = proc.communicate(input=json.dumps(payload, default=str).encode('utf-8'), timeout=60)
            result = json.loads(out.decode('utf-8'))
            if result.get('success'):
                return True, result.get('gmc_product_id', '')
            return False, result.get('error', 'Unknown error')
        except Exception as e:
            _logger.warning('GMC subprocess insert failed: %s', e)
            return False, str(e)

    def delete_product(self, offer_id, content_language='fr', feed_label='BE'):
        """Delete product input by offer_id."""
        if not self.credentials_json:
            return False, 'No credentials configured'
        if _use_subprocess():
            return self._delete_via_subprocess(offer_id, content_language, feed_label)
        client = self._get_client()
        if not client:
            return False, 'No credentials configured'
        name = 'accounts/%s/productInputs/%s~%s~%s' % (
            self.merchant_id, content_language, feed_label, offer_id
        )
        try:
            from google.shopping import merchant_products_v1
            request = merchant_products_v1.DeleteProductInputRequest(
                name=name,
                data_source=self.data_source,
            )
            client.delete_product_input(request=request)
            return True, None
        except Exception as e:
            _logger.warning('GMC delete_product failed: %s', e)
            return False, str(e)

    def _delete_via_subprocess(self, offer_id, content_language='fr', feed_label='BE'):
        payload = {
            'action': 'delete',
            'merchant_id': self.merchant_id,
            'data_source_id': self.data_source_id,
            'credentials_json': self.credentials_json,
            'offer_id': offer_id,
            'content_language': content_language,
            'feed_label': feed_label,
        }
        try:
            env = os.environ.copy()
            env['PYTHONPATH'] = GMC_LIBS_PATH
            proc = subprocess.Popen(
                ['python3', _script_path()],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=os.path.dirname(_script_path()),
            )
            out, err = proc.communicate(input=json.dumps(payload).encode('utf-8'), timeout=30)
            result = json.loads(out.decode('utf-8'))
            if result.get('success'):
                return True, None
            return False, result.get('error', 'Unknown error')
        except Exception as e:
            _logger.warning('GMC subprocess delete failed: %s', e)
            return False, str(e)

    def insert_product_with_retry(self, product_data, max_retries=3):
        """Insert with exponential backoff."""
        for attempt in range(max_retries):
            ok, result = self.insert_product(product_data)
            if ok:
                return ok, result
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        return False, result
