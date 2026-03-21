#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Load GMC offer_id mapping into product.template.gmc_offer_id field.

Reads gmc_existing_mapping.json and sets the gmc_offer_id field on matching
products so that the first API sync preserves existing Google history.

Usage:
  docker exec -i CONTAINER odoo shell -d DB < this_script.py
"""
from __future__ import print_function
import json
import os
import sys

try:
    env
except NameError:
    print("Run via Odoo shell", file=sys.stderr)
    sys.exit(1)

try:
    MAPPING_FILE = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'gmc_existing_mapping.json'
    )
except NameError:
    MAPPING_FILE = '/mnt/extra-addons/google_merchant_center/gmc_existing_mapping.json'

if not os.path.isfile(MAPPING_FILE):
    print("Mapping file not found", file=sys.stderr)
    sys.exit(1)

with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
    mapping = json.load(f)

print("Loaded %d entries from mapping" % len(mapping), file=sys.stderr)

Product = env['product.template'].sudo()
updated = 0
not_found = 0

for odoo_id_str, data in mapping.items():
    try:
        odoo_id = int(odoo_id_str)
    except ValueError:
        continue
    product = Product.browse(odoo_id)
    if not product.exists():
        print("  Product ID %d not found" % odoo_id, file=sys.stderr)
        not_found += 1
        continue
    offer_id = data.get('gmc_offer_id', '')
    if offer_id and product.gmc_offer_id != offer_id:
        product.with_context(gmc_skip_write_trigger=True).write({
            'gmc_offer_id': offer_id,
        })
        updated += 1

env.cr.commit()
print("\nDone: %d updated, %d not found" % (updated, not_found), file=sys.stderr)
