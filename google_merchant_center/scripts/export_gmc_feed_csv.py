#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export the same product data that is sent to Google Merchant Center to a CSV file.
Use this to review and optimize titles, descriptions, categories, and conversion
without using the Odoo UI or hitting the live API.

Usage (from project root, Docker running):
  docker exec -i freemoov-odoo16-test odoo shell -d freemoov-prod-v16 < google_merchant_center/scripts/export_gmc_feed_csv.py

Output: google_merchant_center/gmc_feed_simulation.csv (in the mounted addons path)

Or to write to a custom path (e.g. /tmp/gmc.csv inside container), set env ODOO_GMC_CSV_PATH.
By default exports all published, non-excluded products. Set GMC_SCOPE_ONLY=1 to restrict to products in GMC scope.
"""
from __future__ import print_function

import csv
import os
import sys

# When run via: odoo shell -d DB < this_script.py
# 'env' is the Odoo environment (injected by shell)
try:
    env
except NameError:
    print("Run this script with: docker exec -i CONTAINER odoo shell -d DB < export_gmc_feed_csv.py", file=sys.stderr)
    sys.exit(1)

OUTPUT_PATH = os.environ.get(
    'ODOO_GMC_CSV_PATH',
    '/mnt/extra-addons/google_merchant_center/gmc_feed_simulation.csv'
)
SCOPE_ONLY = os.environ.get('GMC_SCOPE_ONLY') == '1'

def main():
    Product = env['product.template']
    products = Product.search([
        ('is_published', '=', True),
        ('gmc_exclude', '=', False),
    ])
    if SCOPE_ONLY:
        products = products.filtered(lambda p: p._is_in_gmc_scope())
    else:
        # Only trottinettes and accessoires; exclude scooters and motos
        products = products.filtered(lambda p: p._is_gmc_product_type_allowed())
    products = products.sorted(key=lambda p: (p.default_code or p.name or ''))

    rows = []
    for product in products:
        data = product._prepare_gmc_product_input()
        title = data.get('title', '')
        desc = data.get('description', '')
        additional = data.get('additional_image_links') or []
        gtin = (data.get('gtin') or '').strip()
        price_eur = (data.get('price_micros') or 0) / 1_000_000

        title_len = len(title)
        desc_len = len(desc)
        has_gtin = 'yes' if gtin else 'no'
        num_extra_images = len(additional)

        hints = []
        if title_len > 150:
            hints.append('title>150')
        elif title_len < 30:
            hints.append('title<30')
        if desc_len > 5000:
            hints.append('desc>5000')
        elif desc_len < 100:
            hints.append('desc<100')
        if not gtin:
            hints.append('no_gtin')
        if num_extra_images == 0 and hasattr(product, 'product_template_image_ids') and product.product_template_image_ids:
            hints.append('add_images')
        hints_str = '; '.join(hints) if hints else ''

        rows.append({
            'id': data.get('offer_id', ''),
            'title': title,
            'title_length': title_len,
            'description': desc,
            'description_length': desc_len,
            'link': data.get('link', ''),
            'image_link': data.get('image_link', ''),
            'additional_image_links': '|'.join(additional),
            'num_additional_images': num_extra_images,
            'availability': data.get('availability', ''),
            'condition': data.get('condition', 'new'),
            'google_product_category': data.get('google_product_category', ''),
            'gtin': gtin,
            'mpn': (data.get('mpn') or '')[:70],
            'brand': (data.get('brand') or '')[:70],
            'price_eur': '%.2f' % price_eur,
            'currency': data.get('currency_code', 'EUR'),
            'shipping_weight_kg': data.get('shipping_weight_value') or '',
            'content_language': data.get('content_language', 'fr'),
            'feed_label': data.get('feed_label', 'BE'),
            'has_gtin': has_gtin,
            'seo_hints': hints_str,
            'product_id_odoo': product.id,
        })

    fieldnames = [
        'id', 'title', 'title_length', 'description', 'description_length',
        'link', 'image_link', 'additional_image_links', 'num_additional_images',
        'availability', 'condition', 'google_product_category', 'gtin', 'mpn', 'brand',
        'price_eur', 'currency', 'shipping_weight_kg',
        'content_language', 'feed_label', 'has_gtin', 'seo_hints', 'product_id_odoo',
    ]

    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)

    print('Exported %d products to %s' % (len(rows), OUTPUT_PATH), file=sys.stderr)
    if not rows:
        print('No products found (published + not excluded).', file=sys.stderr)

main()
