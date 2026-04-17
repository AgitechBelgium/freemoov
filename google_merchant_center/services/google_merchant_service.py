# -*- coding: utf-8 -*-
# Enzo Nauté — 2026
"""
Client Google Merchant API via REST (merchantapi.googleapis.com).
Utilise google-auth + requests, zero dependance protobuf/gRPC.
"""
import json
import logging
import time

_logger = logging.getLogger(__name__)

API_BASE = 'https://merchantapi.googleapis.com/products/v1'
SCOPES = ['https://www.googleapis.com/auth/content']


def _get_session(credentials_json):
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_info(
        credentials_json, scopes=SCOPES,
    )
    return AuthorizedSession(creds)


def _build_product_body(product_data):
    """Build REST JSON body for InsertProductInput from product_data dict."""
    attrs = {}

    if product_data.get('title'):
        attrs['title'] = product_data['title'][:150]
    if product_data.get('description'):
        attrs['description'] = product_data['description'][:5000]
    if product_data.get('link'):
        attrs['link'] = product_data['link']
    if product_data.get('image_link'):
        attrs['imageLink'] = product_data['image_link']
    if product_data.get('additional_image_links'):
        attrs['additionalImageLinks'] = product_data['additional_image_links'][:10]

    avail = (product_data.get('availability') or 'IN_STOCK').upper().replace(' ', '_')
    attrs['availability'] = avail

    cond = (product_data.get('condition') or 'new').upper()
    attrs['condition'] = cond

    if product_data.get('price_micros'):
        attrs['price'] = {
            'amountMicros': str(int(product_data['price_micros'])),
            'currencyCode': product_data.get('currency_code', 'EUR'),
        }
    if product_data.get('sale_price_micros'):
        attrs['salePrice'] = {
            'amountMicros': str(int(product_data['sale_price_micros'])),
            'currencyCode': product_data.get('currency_code', 'EUR'),
        }

    if product_data.get('google_product_category'):
        attrs['googleProductCategory'] = str(product_data['google_product_category'])

    if product_data.get('product_type'):
        attrs['productTypes'] = [str(product_data['product_type'])]

    if product_data.get('brand'):
        attrs['brand'] = product_data['brand'][:70]
    if product_data.get('gtin'):
        attrs['gtins'] = [str(product_data['gtin'])]
    if product_data.get('mpn'):
        attrs['mpn'] = product_data['mpn'][:70]

    if not product_data.get('identifier_exists', True):
        attrs['identifierExists'] = False

    if product_data.get('shipping_weight_value') and product_data['shipping_weight_value'] > 0:
        attrs['shippingWeight'] = {
            'value': float(product_data['shipping_weight_value']),
            'unit': product_data.get('shipping_weight_unit', 'kg'),
        }

    if product_data.get('shipping'):
        shipping_list = []
        for s in product_data['shipping']:
            shipping_list.append({
                'country': s.get('country', 'BE'),
                'price': {
                    'amountMicros': str(int(s.get('price_micros', 0))),
                    'currencyCode': s.get('currency_code', 'EUR'),
                },
            })
        attrs['shipping'] = shipping_list

    for i in range(5):
        key = 'custom_label_%d' % i
        camel = 'customLabel%d' % i
        val = product_data.get(key)
        if val:
            attrs[camel] = str(val)[:100]

    body = {
        'offerId': str(product_data.get('offer_id', ''))[:50],
        'contentLanguage': product_data.get('content_language', 'fr'),
        'feedLabel': product_data.get('feed_label', 'BE'),
        'productAttributes': attrs,
    }
    return body


class GoogleMerchantService(object):
    """Sync products with Google Merchant Center via REST API."""

    def __init__(self, merchant_id, data_source_id, credentials_json):
        self.merchant_id = str(merchant_id)
        self.data_source_id = str(data_source_id)
        self.credentials_json = credentials_json
        self._session = None

    def _get_session(self):
        if self._session is None and self.credentials_json:
            self._session = _get_session(self.credentials_json)
        return self._session

    @property
    def parent(self):
        return 'accounts/%s' % self.merchant_id

    @property
    def data_source(self):
        return 'accounts/%s/dataSources/%s' % (self.merchant_id, self.data_source_id)

    def insert_product(self, product_data):
        """Insert or update (upsert) a product. Returns (success, response_or_error)."""
        if not self.credentials_json:
            return False, 'No credentials configured'
        session = self._get_session()
        if not session:
            return False, 'Could not create authenticated session'
        try:
            url = '%s/%s/productInputs:insert' % (API_BASE, self.parent)
            body = _build_product_body(product_data)
            resp = session.post(url, json=body, params={'dataSource': self.data_source})
            if resp.status_code in (200, 201):
                return True, resp.json()
            error_msg = resp.text[:500]
            _logger.warning('GMC insert failed (%s): %s', resp.status_code, error_msg)
            return False, error_msg
        except Exception as e:
            _logger.warning('GMC insert_product exception: %s', e)
            return False, str(e)

    def delete_product(self, offer_id, content_language='fr', feed_label='BE'):
        """Delete product input by offer_id."""
        if not self.credentials_json:
            return False, 'No credentials configured'
        session = self._get_session()
        if not session:
            return False, 'Could not create authenticated session'
        name = '%s/productInputs/%s~%s~%s' % (
            self.parent, content_language, feed_label, offer_id,
        )
        try:
            url = '%s/%s' % (API_BASE, name)
            resp = session.delete(url, params={'dataSource': self.data_source})
            if resp.status_code in (200, 204, 404):
                return True, None
            error_msg = resp.text[:500]
            _logger.warning('GMC delete failed (%s): %s', resp.status_code, error_msg)
            return False, error_msg
        except Exception as e:
            _logger.warning('GMC delete_product exception: %s', e)
            return False, str(e)

    def list_products(self, page_size=250):
        """List all products in the account. Returns (success, products_list_or_error)."""
        if not self.credentials_json:
            return False, 'No credentials configured'
        session = self._get_session()
        if not session:
            return False, 'Could not create authenticated session'
        try:
            url = '%s/%s/products' % (API_BASE, self.parent)
            products = []
            page_token = None
            while True:
                params = {'pageSize': page_size}
                if page_token:
                    params['pageToken'] = page_token
                resp = session.get(url, params=params)
                if resp.status_code != 200:
                    return False, resp.text[:500]
                data = resp.json()
                products.extend(data.get('products', []))
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            return True, products
        except Exception as e:
            _logger.warning('GMC list_products exception: %s', e)
            return False, str(e)

    def insert_product_with_retry(self, product_data, max_retries=3):
        """Insert with exponential backoff."""
        last_error = None
        for attempt in range(max_retries):
            ok, result = self.insert_product(product_data)
            if ok:
                return ok, result
            last_error = result
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        return False, last_error
