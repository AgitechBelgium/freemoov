#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GMC Feed Optimizer — Conforme aux specifications Google Merchant Center
https://support.google.com/merchants/answer/7052112?hl=fr

Genere deux fichiers :
  - gmc_feed_optimized.csv : flux conforme Google (tous les attributs requis + recommandes)
  - gmc_feed_audit.csv     : rapport avant/apres + actions a mener

Usage:
  docker exec -i freemoov-odoo16-test odoo shell -d freemoov-prod-v16 \
    < google_merchant_center/scripts/optimize_gmc_feed.py
"""
from __future__ import print_function
import csv
from datetime import datetime, timedelta
import json
import re
import os
import sys

try:
    env
except NameError:
    print("Run via: docker exec -i CONTAINER odoo shell -d DB < this_script.py", file=sys.stderr)
    sys.exit(1)

BASE_PATH = '/mnt/extra-addons/google_merchant_center'
OUTPUT_OPTIMIZED = os.path.join(BASE_PATH, 'gmc_feed_optimized.csv')
OUTPUT_AUDIT = os.path.join(BASE_PATH, 'gmc_feed_audit.csv')
BASE_URL = 'https://freemoov.com'

# ══════════════════════════════════════════════════════════════════════
# Mapping GMC existant — preserve les offer_id pour eviter DELETE+ADD
# Fichier genere par: python3 (local) avec gmc_api_runner.py action=list
# Structure: { "odoo_template_id": { "gmc_offer_id": "...", ... } }
# ══════════════════════════════════════════════════════════════════════
GMC_MAPPING_FILE = os.path.join(BASE_PATH, 'gmc_existing_mapping.json')
GMC_MAPPING = {}
if os.path.isfile(GMC_MAPPING_FILE):
    try:
        with open(GMC_MAPPING_FILE, 'r', encoding='utf-8') as _f:
            GMC_MAPPING = json.load(_f)
        print('GMC mapping charge: %d produits existants' % len(GMC_MAPPING), file=sys.stderr)
    except Exception as _e:
        print('GMC mapping erreur: %s' % _e, file=sys.stderr)
else:
    print('GMC mapping non trouve (%s) — nouveaux offer_id pour tous' % GMC_MAPPING_FILE, file=sys.stderr)

# ══════════════════════════════════════════════════════════════════════
# google_product_category — IDs numeriques de la taxonomie Google
# ══════════════════════════════════════════════════════════════════════
GPC = {
    'trottinette':       5879,   # Sporting Goods > Outdoor Recreation > Riding Scooters
    'pneu':              4571,   # Cycling > Bicycle Parts > Bicycle Tires
    'chambre_air':       4572,   # Cycling > Bicycle Parts > Bicycle Tubes
    'casque':            1029,   # Cycling > Cycling Apparel > Bicycle Helmets
    'gant':              3246,   # Cycling > Cycling Apparel > Bicycle Gloves
    'chargeur':          505295, # Electronics > Power Adapters & Chargers
    'antivol':           1027,   # Cycling > Bicycle Accessories > Bicycle Locks
    'frein':             3740,   # Cycling > Bicycle Parts > Bicycle Brake Parts
    'piece_electronique':3618,   # Cycling > Bicycle Parts
    'piece_detachee':    3618,   # Cycling > Bicycle Parts
    'accessoire':        3214,   # Cycling > Bicycle Accessories
    'equipement':        3214,   # Cycling > Bicycle Accessories
    'velo':              3070,   # Cycling > Bicycles > Electric Bicycles
    'default':           5879,
}

PTYPE = {
    'trottinette':        'Mobilite electrique > Trottinette electrique',
    'pneu':               'Mobilite electrique > Pieces detachees > Pneus et chambres a air',
    'chambre_air':        'Mobilite electrique > Pieces detachees > Pneus et chambres a air',
    'casque':             'Mobilite electrique > Equipement > Casques',
    'gant':               'Mobilite electrique > Equipement > Gants',
    'chargeur':           'Mobilite electrique > Pieces detachees > Chargeurs',
    'antivol':            'Mobilite electrique > Accessoires > Antivols',
    'frein':              'Mobilite electrique > Pieces detachees > Freins',
    'piece_electronique': 'Mobilite electrique > Pieces detachees > Electronique',
    'piece_detachee':     'Mobilite electrique > Pieces detachees',
    'accessoire':         'Mobilite electrique > Accessoires',
    'equipement':         'Mobilite electrique > Equipement',
    'velo':               'Mobilite electrique > Velo electrique',
}

# ══════════════════════════════════════════════════════════════════════
# Nettoyage description — approche agressive comme le PHP :
# strip HTML, strip URLs, normaliser TOUS les espaces,
# fusionner les listes a puces en phrases fluides,
# sortie = texte plat, une seule ligne continue (pas de \n)
# ══════════════════════════════════════════════════════════════════════

def clean_description(raw):
    """
    Nettoyage agressif de la description :
    1. Supprime toutes les balises HTML
    2. Supprime toutes les URLs (liens fournisseurs, etc.)
    3. Supprime les nbsp et entites HTML
    4. Convertit les listes a puces en virgules
    5. Normalise tous les espaces (y compris \n, \t, \xa0) en un seul espace
    6. Resultat : un texte plat, propre, sans saut de ligne
    """
    if not raw:
        return ''
    text = raw

    # Remove <img> tags (often contain supplier image links)
    text = re.sub(r'<img[^>]*>', ' ', text, flags=re.IGNORECASE)

    # Convert <br>, </p>, </div>, </li>, </h*> to a separator
    text = re.sub(r'<br\s*/?>', ' | ', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:p|div|h[1-6]|tr|section|article)>', ' | ', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', ', ', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', ' ', text, flags=re.IGNORECASE)

    # Strip ALL remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('\xa0', ' ')  # non-breaking space
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&euro;', 'EUR')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)

    # Remove ALL URLs
    text = re.sub(r'https?://[^\s,;|)\"\'<>]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'www\.[^\s,;|)\"\'<>]+', '', text, flags=re.IGNORECASE)

    # Remove supplier/internal references patterns
    text = re.sub(r'[Ll]ien\s+fournisseur\s*:?', '', text)
    text = re.sub(r'[Rr][ée]f(?:[ée]rence)?\s+fournisseur\s*:?', '', text)
    text = re.sub(r'[Ss]ource\s*:\s*', '', text)

    # Normalize bullet points: "- item" or "• item" -> ", item"
    text = re.sub(r'[\n\r]+\s*[-•·▪►➤]\s*', ', ', text)
    text = re.sub(r'^\s*[-•·▪►➤]\s*', '', text)

    # Replace all newlines, tabs with a space
    text = text.replace('\n', ' ')
    text = text.replace('\r', ' ')
    text = text.replace('\t', ' ')

    # Clean up separators: " | , " or " | | " or ", , "
    text = re.sub(r'\s*\|\s*,\s*', '. ', text)
    text = re.sub(r'\s*\|\s*\|\s*', '. ', text)
    text = re.sub(r',\s*,\s*', ', ', text)
    text = re.sub(r'\s*\|\s*', '. ', text)

    # Multiple dots -> single
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\.\s*\.', '.', text)

    # Multiple commas -> single
    text = re.sub(r',\s*,', ',', text)

    # Remove leading comma/dot after sentence start
    text = re.sub(r'^\s*[.,]\s*', '', text)

    # Normalize ALL whitespace to single space
    text = re.sub(r'\s+', ' ', text)

    # Clean up leading/trailing punctuation issues
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)  # no space before punctuation
    text = re.sub(r'([.,;:!?])\s*([.,;:!?])', r'\1', text)  # no double punctuation

    # Ensure first letter is uppercase
    text = text.strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    # Ensure ends with a period
    if text and text[-1] not in '.!?':
        text += '.'

    return text.strip()


# ══════════════════════════════════════════════════════════════════════
# Detection du type de produit
# ══════════════════════════════════════════════════════════════════════
def detect_type(title_lower, cat_names):
    if 'trottinette' in title_lower:
        return 'trottinette'
    all_t = title_lower + ' ' + ' '.join(cat_names)
    # Velo : seulement si titre contient explicitement velo/fatbike OU
    # marque velo + pas un accessoire evident
    velo_explicit = any(kw in title_lower for kw in ['vélo', 'velo', 'fatbike', 'fat bike'])
    velo_brand = any(kw in title_lower for kw in ['phatfour fl', 'lombardo', 'super73', 'littium', 'knaap'])
    accessoire_keywords = ['bac ', 'cargo ', 'batterie', 'chargeur', 'panier', 'porte-bagage',
        'porte bagage', 'repose-pied', 'siège', 'siege', 'support', 'traceur', 'gps',
        'sacoche', 'rétroviseur', 'béquille', 'garde-boue', 'clignotant', 'poignée']
    is_accessoire = any(kw in title_lower for kw in accessoire_keywords)
    if velo_explicit and not is_accessoire:
        return 'velo'
    if velo_brand and not is_accessoire:
        return 'velo'
    checks = [
        (['pneu plein', 'pneu route', 'pneu offroad', 'pneu off road', 'pneu tubeless', 'pneu semi'], 'pneu'),
        (['chambre a air', 'chambre \xe0 air'], 'chambre_air'),
        (['casque'], 'casque'),
        (['gant'], 'gant'),
        (['chargeur', 'alimentation'], 'chargeur'),
        (['antivol', 'cadenas', 'cable antivol', 'c\xe2ble antivol'], 'antivol'),
        (['plaquette', 'disque de frein', 'etrier de frein', '\xe9trier de frein'], 'frein'),
        (['controleur', 'contr\xf4leur', 'moteur brushless', 'afficheur', 'display', 'batterie'], 'piece_electronique'),
        (['valve', 'roulement', 'grip', 'garde-boue', 'b\xe9quille', 'bequille'], 'piece_detachee'),
        (['sacoche', 'support', 'r\xe9troviseur', 'retroviseur', 'clignotant', 'klaxon',
          'sonnette', 'pompe', 'gonflage', 'visibilit\xe9', 'poign\xe9e'], 'accessoire'),
        (['\xe9quipement', 'equipement', 'gilet'], 'equipement'),
    ]
    for keywords, ptype in checks:
        if any(kw in all_t for kw in keywords):
            return ptype
    if any(kw in all_t for kw in ['pi\xe8ce', 'piece', 'roue']):
        return 'piece_detachee'
    return 'accessoire'


# ══════════════════════════════════════════════════════════════════════
# Titre SEO — max 150 caracteres
# ══════════════════════════════════════════════════════════════════════
def build_title(product, brand, raw_title, ptype):
    if ptype == 'trottinette':
        model = raw_title
        for pfx in ['Trottinette \xe9lectrique ', 'Trottinette Electrique ',
                     'Trottinette \xc9lectrique ', 'Trottinette electrique ']:
            model = model.replace(pfx, '')
        model = model.strip(' -\u2013')
        if brand:
            bn = brand.lower().replace('-', ' ').strip()
            mn = model.lower().replace('-', ' ').strip()
            if mn.startswith(bn):
                model = model[len(bn):].strip(' -\u2013')
            elif model.lower().startswith(brand.lower()):
                model = model[len(brand):].strip(' -\u2013')

        specs = []
        v = re.search(r'(\d+)\s*[Vv]', raw_title)
        a = re.search(r'(\d+[.,]?\d*)\s*[Aa][Hh]', raw_title)
        w = re.search(r'(\d+)\s*[Ww]', raw_title)
        if v: specs.append('%sV' % v.group(1))
        if a: specs.append('%s Ah' % a.group(1).replace(',', '.'))
        if w and not v: specs.append('%sW' % w.group(1))
        spec_str = ' / '.join(specs)

        if spec_str:
            title = '%s %s - Trottinette \xe9lectrique - %s' % (brand, model, spec_str)
        else:
            title = '%s %s - Trottinette \xe9lectrique' % (brand, model)
    elif ptype == 'velo':
        model = raw_title
        velo_prefixes = ['V\xe9lo \xe9lectrique Fatbike ', 'V\xe9lo \xe9lectrique pliable ',
                         'V\xe9lo \xe9lectrique ', 'Velo electrique ',
                         'Fatbike ', 'FATBIKE ', 'Fat Bike ', 'Fat bike ']
        for pfx in velo_prefixes:
            model = model.replace(pfx, '')
        # Also handle actual unicode
        for pfx in ['V\u00e9lo \u00e9lectrique Fatbike ', 'V\u00e9lo \u00e9lectrique pliable ',
                     'V\u00e9lo \u00e9lectrique ']:
            model = model.replace(pfx, '')
        model = model.strip(' -\u2013')
        # If brand is Freemoov (fallback), extract real brand from model
        velo_brands = ['knaap', 'phatfour', 'lombardo', 'super73', 'littium']
        if brand == 'Freemoov' or not brand:
            for vb in velo_brands:
                if vb in model.lower():
                    idx = model.lower().find(vb)
                    # Extract the brand as it appears in model (preserve case)
                    end = idx + len(vb)
                    while end < len(model) and model[end] != ' ':
                        end += 1
                    brand = model[idx:end]
                    break
        if brand:
            bn = brand.lower().replace('-', ' ').strip()
            mn = model.lower().replace('-', ' ').strip()
            if mn.startswith(bn):
                model = model[len(bn):].strip(' -\u2013')
            elif model.lower().startswith(brand.lower()):
                model = model[len(brand):].strip(' -\u2013')
        if 'pliable' in raw_title.lower():
            title = '%s %s - V\xe9lo \xe9lectrique pliable' % (brand, model)
        elif 'fatbike' in raw_title.lower() or 'fat bike' in raw_title.lower():
            title = '%s %s - Fatbike \xe9lectrique' % (brand, model)
        else:
            title = '%s %s - V\xe9lo \xe9lectrique' % (brand, model)
    else:
        type_suffix = {
            'pneu': 'Pneu trottinette \xe9lectrique',
            'chambre_air': 'Chambre \xe0 air trottinette \xe9lectrique',
            'casque': 'Casque mobilit\xe9 \xe9lectrique',
            'gant': 'Gants mobilit\xe9 \xe9lectrique',
            'chargeur': 'Chargeur trottinette \xe9lectrique',
            'antivol': 'Antivol trottinette \xe9lectrique',
            'frein': 'Pi\xe8ce frein trottinette \xe9lectrique',
            'piece_electronique': 'Pi\xe8ce d\xe9tach\xe9e trottinette \xe9lectrique',
            'piece_detachee': 'Pi\xe8ce d\xe9tach\xe9e trottinette \xe9lectrique',
            'accessoire': 'Accessoire trottinette \xe9lectrique',
            'equipement': '\xc9quipement mobilit\xe9 \xe9lectrique',
        }.get(ptype, 'Accessoire trottinette \xe9lectrique')

        # Accessoire de velo? Adapter le suffixe
        velo_brand_list = ['phatfour', 'knaap', 'lombardo', 'super73', 'littium']
        if any(vb in raw_title.lower() for vb in velo_brand_list):
            type_suffix = type_suffix.replace('trottinette \xe9lectrique', 'v\xe9lo \xe9lectrique')
        if 'trottinette' in raw_title.lower() or 'compatible' in raw_title.lower():
            title = raw_title
        elif brand and brand.lower() not in raw_title.lower() and brand != 'Freemoov':
            title = '%s %s - %s' % (brand, raw_title, type_suffix)
        else:
            title = '%s - %s' % (raw_title, type_suffix)

    return title[:150].strip(' -\u2013')


# ══════════════════════════════════════════════════════════════════════
# Description finale — texte plat, SEO, max 5000 car.
# ══════════════════════════════════════════════════════════════════════
def build_description(product, brand, ptype, raw_summary, raw_desc_sale):
    raw = raw_summary or raw_desc_sale or ''
    clean = clean_description(raw)
    product_name = get_fr(product.name) or ''

    type_fr = {
        'trottinette': 'trottinette \xe9lectrique',
        'pneu': 'pneu pour trottinette \xe9lectrique',
        'chambre_air': 'chambre \xe0 air pour trottinette \xe9lectrique',
        'casque': 'casque pour la mobilit\xe9 \xe9lectrique',
        'gant': 'gants pour la mobilit\xe9 \xe9lectrique',
        'chargeur': 'chargeur pour trottinette \xe9lectrique',
        'antivol': 'antivol pour trottinette \xe9lectrique',
        'frein': 'pi\xe8ce de frein pour trottinette \xe9lectrique',
        'piece_electronique': 'pi\xe8ce \xe9lectronique pour trottinette',
        'piece_detachee': 'pi\xe8ce d\xe9tach\xe9e pour trottinette \xe9lectrique',
        'accessoire': 'accessoire pour trottinette \xe9lectrique',
        'equipement': '\xe9quipement pour la mobilit\xe9 \xe9lectrique',
    }.get(ptype, 'accessoire pour trottinette \xe9lectrique')

    if len(clean) < 50:
        clean = '%s, %s compatible avec de nombreux mod\xe8les de trottinettes \xe9lectriques.' % (
            product_name, type_fr
        )
        if brand and brand != 'Freemoov':
            clean += ' Marque : %s.' % brand

    # Prefix with product name for SEO if not already present
    if product_name and not clean.lower().startswith(product_name.lower()[:20]):
        clean = '%s. %s' % (product_name, clean)

    # Final safety: ensure single-line, no double spaces
    clean = re.sub(r'\s+', ' ', clean).strip()

    # Ensure ends with period
    if clean and clean[-1] not in '.!?':
        clean += '.'

    return clean[:5000].strip()


def get_fr(val):
    if not val: return ''
    if isinstance(val, str): return val
    if isinstance(val, dict): return val.get('fr_BE', val.get('en_US', ''))
    return str(val) if val else ''


def get_cat_names(product):
    names = []
    for cat in product.public_categ_ids:
        c = cat
        while c:
            n = get_fr(c.name)
            if n: names.append(n.lower())
            c = c.parent_id
    return names


def price_label(price_ttc):
    if price_ttc >= 3000: return 'Premium (3000+)'
    if price_ttc >= 1500: return 'Haut de gamme (1500-3000)'
    if price_ttc >= 500:  return 'Milieu de gamme (500-1500)'
    if price_ttc >= 100:  return 'Entree de gamme (100-500)'
    return 'Petit budget (0-100)'


# ══════════════════════════════════════════════════════════════════════
# Tarifs livraison — extraits de delivery_price_rule en production Odoo
# Seuil gratuit: 190 EUR TTC (tous pays)
# Colis lourd (>= 30kg): tarif special
# ══════════════════════════════════════════════════════════════════════
SHIPPING_RATES = {
    'BE': {'standard': 7.90, 'heavy': 49.90},
    'FR': {'standard': 12.90, 'heavy': 79.90},
    'LU': {'standard': 8.90, 'heavy': 58.90},
    'NL': {'standard': 8.90, 'heavy': 58.90},
}
FREE_SHIPPING_THRESHOLD = 190.0

def compute_shipping(country, weight, price_ttc):
    rates = SHIPPING_RATES[country]
    if weight and weight >= 30:
        return rates['heavy']
    if price_ttc >= FREE_SHIPPING_THRESHOLD:
        return 0.0
    return rates['standard']

def estimate_weight(ptype, price_ttc):
    if ptype == 'trottinette':
        if price_ttc >= 3000: return 40.0
        if price_ttc >= 1500: return 25.0
        if price_ttc >= 800:  return 18.0
        return 14.0
    if ptype in ('pneu', 'chambre_air'): return 0.8
    if ptype == 'casque': return 0.6
    if ptype == 'chargeur': return 1.2
    if ptype == 'antivol': return 1.5
    if ptype == 'frein': return 0.3
    if ptype in ('piece_electronique', 'piece_detachee'): return 0.5
    if ptype == 'gant': return 0.2
    if ptype == 'equipement': return 0.4
    return 0.5


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    Product = env['product.template'].with_context(lang='fr_BE')
    products = Product.search([
        ('is_published', '=', True),
        ('gmc_exclude', '=', False),
    ])
    def _in_feed_scope(p):
        title = (p.name or '').lower()
        cats = [c.name.lower() for c in p.public_categ_ids] if p.public_categ_ids else []
        all_text = title + ' ' + ' '.join(cats)
        exclude = ('scooter', 'coopop', 'cyclomoteur', 'brekr', 'gyroroue', 'monoroue')
        return not any(kw in all_text for kw in exclude)
    products = products.filtered(_in_feed_scope)
    products = products.sorted(key=lambda p: (p.default_code or p.name or ''))

    opt_rows = []
    audit_rows = []

    for product in products:
        raw_title = get_fr(product.name) or ''
        title_lower = raw_title.lower()
        cat_names = get_cat_names(product)

        brand = 'Freemoov'
        if hasattr(product, 'brand_id') and product.brand_id and product.brand_id.name:
            brand = product.brand_id.name

        ptype = detect_type(title_lower, cat_names)
        gpc_id = GPC.get(ptype, GPC['default'])
        product_type = PTYPE.get(ptype, 'Mobilite electrique > Accessoires')
        if ptype == 'trottinette' and brand != 'Freemoov':
            product_type += ' > %s' % brand

        opt_title = build_title(product, brand, raw_title, ptype)

        raw_summary = get_fr(product.summary) if hasattr(product, 'summary') and product.summary else ''
        raw_desc = get_fr(product.description_sale) if product.description_sale else ''
        if not raw_desc and product.description:
            raw_desc = get_fr(product.description)
        orig_desc_raw = raw_summary or raw_desc or ''
        orig_desc_clean = clean_description(orig_desc_raw)
        opt_desc = build_description(product, brand, ptype, raw_summary, raw_desc)

        # Google Shopping exige la vitesse max pour les velos motorises
        if ptype == 'velo' and '25 km' not in opt_desc.lower():
            opt_desc = opt_desc.rstrip('.')
            opt_desc += '. Vitesse maximale assistee : 25 km/h. Conforme a la reglementation europeenne EN 15194.'

        # list_price et compare_list_price sont deja TTC (taxe 21% price_include=true)
        price_ttc = float(product.list_price or 0)
        sale_price_ttc = None
        if hasattr(product, 'compare_list_price') and product.compare_list_price and product.compare_list_price > price_ttc:
            sale_price_ttc = price_ttc
            price_ttc = float(product.compare_list_price)

        barcode = ''
        default_code = ''
        if product.product_variant_count == 1 and product.product_variant_ids:
            v = product.product_variant_ids[0]
            barcode = (v.barcode or '').strip()
            default_code = (v.default_code or '').strip()
        # Preserve GMC offer_id si le produit existe deja dans Google Merchant Center
        odoo_id_str = str(product.id)
        if odoo_id_str in GMC_MAPPING:
            offer_id = GMC_MAPPING[odoo_id_str]['gmc_offer_id']
        else:
            offer_id = (default_code or odoo_id_str)[:50]

        has_gtin = bool(barcode)
        has_mpn = bool(default_code)
        identifier_exists = 'yes' if (has_gtin or (has_mpn and brand)) else 'no'

        path = getattr(product, 'website_url', None) or ('/shop/product/%s' % product.id)
        link = BASE_URL + path if path.startswith('/') else path

        image_link = '%s/web/image/product.template/%s/image_1920' % (BASE_URL, product.id)
        add_imgs = []
        if hasattr(product, 'product_template_image_ids') and product.product_template_image_ids:
            for img in product.product_template_image_ids[:10]:
                add_imgs.append('%s/web/image/product.image/%s/image_1920' % (BASE_URL, img.id))

        availability = 'in_stock'
        try:
            av = product._get_gmc_availability()
            availability = av.lower().replace(' ', '_')
            if availability not in ('in_stock', 'out_of_stock', 'preorder', 'backorder'):
                availability = 'in_stock'
        except Exception:
            pass

        # availability_date requis par Google pour preorder/backorder (ISO 8601)
        availability_date = ''
        if availability == 'preorder':
            availability_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S+01:00')
        elif availability == 'backorder':
            availability_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%S+01:00')

        condition = product.gmc_condition or 'new'
        weight = product.weight if product.weight else None

        effective_weight = weight if weight else estimate_weight(ptype, price_ttc)
        ship_be = compute_shipping('BE', effective_weight, price_ttc)
        ship_fr = compute_shipping('FR', effective_weight, price_ttc)
        ship_lu = compute_shipping('LU', effective_weight, price_ttc)
        ship_nl = compute_shipping('NL', effective_weight, price_ttc)
        shipping_label = 'oversized' if effective_weight and effective_weight >= 30 else 'standard'

        cl0 = price_label(price_ttc)
        cl1 = brand[:100]
        cl2 = product_type.split(' > ')[1] if ' > ' in product_type else product_type
        cl2 = cl2[:100]
        cl3 = 'Avec GTIN' if has_gtin else 'Sans GTIN'
        cl4 = 'Images multiples' if add_imgs else 'Image unique'

        opt_rows.append({
            'id': offer_id,
            'title': opt_title,
            'description': opt_desc,
            'link': link,
            'image_link': image_link,
            'additional_image_link': '|'.join(add_imgs),
            'availability': availability,
            'availability_date': availability_date,
            'condition': condition,
            'price': '%.2f EUR' % price_ttc,
            'sale_price': '%.2f EUR' % sale_price_ttc if sale_price_ttc else '',
            'google_product_category': gpc_id,
            'product_type': product_type,
            'brand': brand[:70],
            'gtin': barcode,
            'mpn': (default_code or offer_id)[:70],
            'identifier_exists': identifier_exists,
            'product_weight': '%.2f kg' % effective_weight if effective_weight else '',
            'shipping(country:BE)': 'BE:::%.2f EUR' % ship_be,
            'shipping(country:FR)': 'FR:::%.2f EUR' % ship_fr,
            'shipping(country:LU)': 'LU:::%.2f EUR' % ship_lu,
            'shipping(country:NL)': 'NL:::%.2f EUR' % ship_nl,
            'shipping_label': shipping_label,
            'free_shipping_threshold(country:price_threshold)': 'BE:190.00 EUR',
            'free_shipping_threshold(country:price_threshold) 2': 'FR:190.00 EUR',
            'free_shipping_threshold(country:price_threshold) 3': 'LU:190.00 EUR',
            'free_shipping_threshold(country:price_threshold) 4': 'NL:190.00 EUR',
            'ships_from_country': 'BE',
            'content_language': 'fr',
            'feed_label': 'BE',
            'included_destination': 'Shopping_ads,Free_listings',
            'custom_label_0': cl0,
            'custom_label_1': cl1,
            'custom_label_2': cl2,
            'custom_label_3': cl3,
            'custom_label_4': cl4,
        })

        title_changed = opt_title != raw_title
        desc_changed = opt_desc != orig_desc_clean
        has_newlines = '\n' in opt_desc
        has_multi_spaces = '  ' in opt_desc
        issues = []
        if not has_gtin: issues.append('GTIN manquant')
        if not has_mpn: issues.append('Ref interne manquante')
        if len(opt_desc) < 100: issues.append('Description < 100 car.')
        if not add_imgs: issues.append("Pas d'images supplementaires")
        if not weight: issues.append('Poids estime (%.1f kg)' % effective_weight if effective_weight else 'Poids manquant')
        if len(opt_title) > 150: issues.append('Titre > 150 car.')
        if has_newlines: issues.append('NEWLINE dans description')
        if has_multi_spaces: issues.append('DOUBLE ESPACE dans description')

        audit_rows.append({
            'product_id_odoo': product.id,
            'original_title': raw_title,
            'optimized_title': opt_title,
            'title_len': len(opt_title),
            'title_changed': 'OUI' if title_changed else '',
            'original_desc_len': len(orig_desc_raw),
            'optimized_desc_len': len(opt_desc),
            'desc_changed': 'OUI' if desc_changed else '',
            'google_product_category': gpc_id,
            'product_type': product_type,
            'has_gtin': 'oui' if has_gtin else 'NON',
            'has_mpn': 'oui' if has_mpn else 'NON',
            'has_weight': 'oui' if weight else ('estime' if effective_weight else 'NON'),
            'has_extra_images': len(add_imgs),
            'price_ttc': '%.2f' % price_ttc,
            'identifier_exists': identifier_exists,
            'issues': ' | '.join(issues) if issues else 'OK',
        })

    # Write optimized feed
    opt_fields = [
        'id', 'title', 'description', 'link', 'image_link', 'additional_image_link',
        'availability', 'availability_date', 'condition', 'price', 'sale_price',
        'google_product_category', 'product_type', 'brand', 'gtin', 'mpn',
        'identifier_exists', 'product_weight',
        'shipping(country:BE)', 'shipping(country:FR)', 'shipping(country:LU)', 'shipping(country:NL)',
        'shipping_label',
        'free_shipping_threshold(country:price_threshold)',
        'free_shipping_threshold(country:price_threshold) 2',
        'free_shipping_threshold(country:price_threshold) 3',
        'free_shipping_threshold(country:price_threshold) 4',
        'ships_from_country',
        'content_language', 'feed_label', 'included_destination',
        'custom_label_0', 'custom_label_1', 'custom_label_2', 'custom_label_3', 'custom_label_4',
    ]
    with open(OUTPUT_OPTIMIZED, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=opt_fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(opt_rows)

    # Write audit
    aud_fields = [
        'product_id_odoo', 'original_title', 'optimized_title', 'title_len', 'title_changed',
        'original_desc_len', 'optimized_desc_len', 'desc_changed',
        'google_product_category', 'product_type', 'has_gtin', 'has_mpn',
        'has_weight', 'has_extra_images', 'price_ttc', 'identifier_exists', 'issues',
    ]
    with open(OUTPUT_AUDIT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=aud_fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(audit_rows)

    # Stats
    total = len(opt_rows)
    descs_with_nl = sum(1 for r in opt_rows if '\n' in r['description'])
    descs_with_dblsp = sum(1 for r in opt_rows if '  ' in r['description'])
    print('\n=== GMC Feed Optimizer — Conforme spec Google ===', file=sys.stderr)
    print('Total produits: %d' % total, file=sys.stderr)
    print('Titres optimises: %d (max 150 car.)' % sum(1 for r in audit_rows if r['title_changed'] == 'OUI'), file=sys.stderr)
    print('Descriptions nettoyees: %d (max 5000 car.)' % sum(1 for r in audit_rows if r['desc_changed'] == 'OUI'), file=sys.stderr)
    print('Descriptions avec \\n: %d' % descs_with_nl, file=sys.stderr)
    print('Descriptions avec double espace: %d' % descs_with_dblsp, file=sys.stderr)
    print('GTIN manquants: %d' % sum(1 for r in audit_rows if r['has_gtin'] == 'NON'), file=sys.stderr)
    print('Poids Odoo: %d | Poids estimes: %d | Poids manquants: %d' % (sum(1 for r in audit_rows if r['has_weight'] == 'oui'), sum(1 for r in audit_rows if r['has_weight'] == 'estime'), sum(1 for r in audit_rows if r['has_weight'] == 'NON')), file=sys.stderr)
    print('Sans images sup.: %d' % sum(1 for r in audit_rows if r['has_extra_images'] == 0), file=sys.stderr)
    print('Desc < 100 car.: %d' % sum(1 for r in audit_rows if r['optimized_desc_len'] < 100), file=sys.stderr)
    print('identifier_exists=no: %d' % sum(1 for r in audit_rows if r['identifier_exists'] == 'no'), file=sys.stderr)
    print('\nFichiers:', file=sys.stderr)
    print('  Feed: %s' % OUTPUT_OPTIMIZED, file=sys.stderr)
    print('  Audit: %s' % OUTPUT_AUDIT, file=sys.stderr)

main()
