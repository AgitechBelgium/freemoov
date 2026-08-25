# -*- coding: utf-8 -*-
# Enzo Nauté — 2026
"""
Logique d'optimisation du flux Google Merchant Center.
Titres SEO, descriptions nettoyées, catégories Google, shipping, custom labels.
Utilisé par le module Odoo (cron/hooks) et les scripts CSV standalone.
"""
import re
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Google Product Category IDs (taxonomy numerique officielle)
# https://www.google.com/basepages/producttype/taxonomy-with-ids.fr-FR.txt
# ─────────────────────────────────────────────────────────────────────
GPC_MAP = {
    'trottinette':        5879,
    'pneu':               4571,
    'chambre_air':        4572,
    'casque':             1029,
    'gant':               3246,
    'chargeur':           505295,
    'antivol':            1027,
    'frein':              3740,
    'piece_electronique': 3618,
    'piece_detachee':     3618,
    'accessoire':         3214,
    'equipement':         3214,
    'velo':               3070,
}

PRODUCT_TYPE_MAP = {
    'trottinette':        u'Mobilit\xe9 \xe9lectrique > Trottinette \xe9lectrique',
    'pneu':               u'Mobilit\xe9 \xe9lectrique > Pi\xe8ces d\xe9tach\xe9es > Pneus et chambres \xe0 air',
    'chambre_air':        u'Mobilit\xe9 \xe9lectrique > Pi\xe8ces d\xe9tach\xe9es > Pneus et chambres \xe0 air',
    'casque':             u'Mobilit\xe9 \xe9lectrique > \xc9quipement > Casques',
    'gant':               u'Mobilit\xe9 \xe9lectrique > \xc9quipement > Gants',
    'chargeur':           u'Mobilit\xe9 \xe9lectrique > Pi\xe8ces d\xe9tach\xe9es > Chargeurs',
    'antivol':            u'Mobilit\xe9 \xe9lectrique > Accessoires > Antivols',
    'frein':              u'Mobilit\xe9 \xe9lectrique > Pi\xe8ces d\xe9tach\xe9es > Freins',
    'piece_electronique': u'Mobilit\xe9 \xe9lectrique > Pi\xe8ces d\xe9tach\xe9es > \xc9lectronique',
    'piece_detachee':     u'Mobilit\xe9 \xe9lectrique > Pi\xe8ces d\xe9tach\xe9es',
    'accessoire':         u'Mobilit\xe9 \xe9lectrique > Accessoires',
    'equipement':         u'Mobilit\xe9 \xe9lectrique > \xc9quipement',
    'velo':               u'Mobilit\xe9 \xe9lectrique > V\xe9lo \xe9lectrique',
}

SHIPPING_RATES = {
    'BE': {'standard': 7.90,  'heavy': 49.90},
    'FR': {'standard': 12.90, 'heavy': 79.90},
    'LU': {'standard': 8.90,  'heavy': 58.90},
    'NL': {'standard': 8.90,  'heavy': 58.90},
}
FREE_SHIPPING_THRESHOLD = 190.0

EXCLUDE_KEYWORDS = ('scooter', 'coopop', 'cyclomoteur', 'brekr', 'gyroroue', 'monoroue')

VELO_BRANDS = ('knaap', 'phatfour', 'lombardo', 'super73', 'littium')
ACCESSOIRE_KEYWORDS = (
    'bac ', 'cargo ', 'batterie', 'chargeur', 'panier', 'porte-bagage',
    'porte bagage', 'repose-pied', u'si\xe8ge', 'siege', 'support', 'traceur',
    'gps', 'sacoche', u'r\xe9troviseur', u'b\xe9quille', 'garde-boue',
    'clignotant', u'poign\xe9e',
)


def _get_fr(val):
    """Extract French value from a potentially JSONB / multilang field."""
    if not val:
        return ''
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return val.get('fr_BE', val.get('en_US', ''))
    return str(val) if val else ''


def _get_cat_names(product):
    """All category names for this product (including parents), lowercased."""
    names = []
    for cat in product.public_categ_ids:
        c = cat
        while c:
            n = _get_fr(c.name)
            if n:
                names.append(n.lower())
            c = c.parent_id
    return names


# ─────────────────────────────────────────────────────────────────────
# HTML → plain text cleaner
# ─────────────────────────────────────────────────────────────────────

def clean_description(raw):
    """Aggressive HTML strip → single-line plain text, no URLs, no supplier refs."""
    if not raw:
        return ''
    text = raw
    text = re.sub(r'<img[^>]*>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', ' | ', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:p|div|h[1-6]|tr|section|article)>', ' | ', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', ', ', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)

    text = text.replace('&nbsp;', ' ')
    text = text.replace(u'\xa0', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&euro;', 'EUR')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)

    text = re.sub(r'https?://[^\s,;|)\"\'<>]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'www\.[^\s,;|)\"\'<>]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[Ll]ien\s+fournisseur\s*:?', '', text)
    text = re.sub(r'[Rr][ée]f(?:[ée]rence)?\s+fournisseur\s*:?', '', text)
    text = re.sub(r'[Ss]ource\s*:\s*', '', text)

    text = re.sub(r'[\n\r]+\s*[-\u2022\u00b7\u25aa\u25ba\u279e]\s*', ', ', text)
    text = re.sub(r'^\s*[-\u2022\u00b7\u25aa\u25ba\u279e]\s*', '', text)
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')

    text = re.sub(r'\s*\|\s*,\s*', '. ', text)
    text = re.sub(r'\s*\|\s*\|\s*', '. ', text)
    text = re.sub(r',\s*,\s*', ', ', text)
    text = re.sub(r'\s*\|\s*', '. ', text)
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\.\s*\.', '.', text)
    text = re.sub(r',\s*,', ',', text)
    text = re.sub(r'^\s*[.,]\s*', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    text = re.sub(r'([.,;:!?])\s*([.,;:!?])', r'\1', text)

    text = text.strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    if text and text[-1] not in '.!?':
        text += '.'
    return text.strip()


# ─────────────────────────────────────────────────────────────────────
# Product type detection
# ─────────────────────────────────────────────────────────────────────

def detect_type(title_lower, cat_names):
    """Detect product type from title + category names."""
    if 'trottinette' in title_lower:
        return 'trottinette'

    all_t = title_lower + ' ' + ' '.join(cat_names)

    velo_explicit = any(kw in title_lower for kw in (u'v\xe9lo', 'velo', 'fatbike', 'fat bike'))
    velo_brand = any(kw in title_lower for kw in ('phatfour fl', 'lombardo', 'super73', 'littium', 'knaap'))
    is_accessoire = any(kw in title_lower for kw in ACCESSOIRE_KEYWORDS)
    if velo_explicit and not is_accessoire:
        return 'velo'
    if velo_brand and not is_accessoire:
        return 'velo'

    checks = [
        (['pneu plein', 'pneu route', 'pneu offroad', 'pneu off road', 'pneu tubeless', 'pneu semi'], 'pneu'),
        (['chambre a air', u'chambre \xe0 air'], 'chambre_air'),
        (['casque'], 'casque'),
        (['gant'], 'gant'),
        (['chargeur', 'alimentation'], 'chargeur'),
        (['antivol', 'cadenas', 'cable antivol', u'c\xe2ble antivol'], 'antivol'),
        (['plaquette', 'disque de frein', 'etrier de frein', u'\xe9trier de frein'], 'frein'),
        (['controleur', u'contr\xf4leur', 'moteur brushless', 'afficheur', 'display', 'batterie'], 'piece_electronique'),
        (['valve', 'roulement', 'grip', 'garde-boue', u'b\xe9quille', 'bequille'], 'piece_detachee'),
        (['sacoche', 'support', u'r\xe9troviseur', 'retroviseur', 'clignotant', 'klaxon',
          'sonnette', 'pompe', 'gonflage', u'visibilit\xe9', u'poign\xe9e'], 'accessoire'),
        ([u'\xe9quipement', 'equipement', 'gilet'], 'equipement'),
    ]
    for keywords, ptype in checks:
        if any(kw in all_t for kw in keywords):
            return ptype

    if any(kw in all_t for kw in (u'pi\xe8ce', 'piece', 'roue')):
        return 'piece_detachee'
    return 'accessoire'


# ─────────────────────────────────────────────────────────────────────
# SEO Title builder — max 150 chars
# ─────────────────────────────────────────────────────────────────────

def build_title(product, brand, raw_title, ptype):
    """Build SEO-optimized title (max 150 chars)."""
    if ptype == 'trottinette':
        return _build_title_trottinette(brand, raw_title)
    elif ptype == 'velo':
        return _build_title_velo(brand, raw_title)
    else:
        return _build_title_accessory(brand, raw_title, ptype)


def _strip_brand_prefix(model, brand):
    """Remove brand name from the beginning of the model string."""
    if not brand:
        return model
    bn = brand.lower().replace('-', ' ').strip()
    mn = model.lower().replace('-', ' ').strip()
    if mn.startswith(bn):
        model = model[len(bn):].strip(u' -\u2013')
    elif model.lower().startswith(brand.lower()):
        model = model[len(brand):].strip(u' -\u2013')
    return model


def _build_title_trottinette(brand, raw_title):
    model = raw_title
    for pfx in [u'Trottinette \xe9lectrique ', u'Trottinette Electrique ',
                u'Trottinette \xc9lectrique ', u'Trottinette electrique ']:
        model = model.replace(pfx, '')
    model = model.strip(u' -\u2013')
    model = _strip_brand_prefix(model, brand)

    specs = []
    v = re.search(r'(\d+)\s*[Vv]', raw_title)
    a = re.search(r'(\d+[.,]?\d*)\s*[Aa][Hh]', raw_title)
    w = re.search(r'(\d+)\s*[Ww]', raw_title)
    if v:
        specs.append('%sV' % v.group(1))
    if a:
        specs.append('%s Ah' % a.group(1).replace(',', '.'))
    if w and not v:
        specs.append('%sW' % w.group(1))
    spec_str = ' / '.join(specs)

    if spec_str:
        title = u'%s %s - Trottinette \xe9lectrique - %s' % (brand, model, spec_str)
    else:
        title = u'%s %s - Trottinette \xe9lectrique' % (brand, model)
    return title[:150].strip(u' -\u2013')


def _build_title_velo(brand, raw_title):
    model = raw_title
    for pfx in [u'V\xe9lo \xe9lectrique Fatbike ', u'V\xe9lo \xe9lectrique pliable ',
                u'V\xe9lo \xe9lectrique ', u'Velo electrique ',
                u'Fatbike ', u'FATBIKE ', u'Fat Bike ', u'Fat bike ']:
        model = model.replace(pfx, '')
    model = model.strip(u' -\u2013')

    if brand == 'Freemoov' or not brand:
        for vb in VELO_BRANDS:
            if vb in model.lower():
                idx = model.lower().find(vb)
                end = idx + len(vb)
                while end < len(model) and model[end] != ' ':
                    end += 1
                brand = model[idx:end]
                break

    model = _strip_brand_prefix(model, brand)

    if 'pliable' in raw_title.lower():
        title = u'%s %s - V\xe9lo \xe9lectrique pliable' % (brand, model)
    elif 'fatbike' in raw_title.lower() or 'fat bike' in raw_title.lower():
        title = u'%s %s - Fatbike \xe9lectrique' % (brand, model)
    else:
        title = u'%s %s - V\xe9lo \xe9lectrique' % (brand, model)
    return title[:150].strip(u' -\u2013')


def _build_title_accessory(brand, raw_title, ptype):
    type_suffix = {
        'pneu':               u'Pneu trottinette \xe9lectrique',
        'chambre_air':        u'Chambre \xe0 air trottinette \xe9lectrique',
        'casque':             u'Casque mobilit\xe9 \xe9lectrique',
        'gant':               u'Gants mobilit\xe9 \xe9lectrique',
        'chargeur':           u'Chargeur trottinette \xe9lectrique',
        'antivol':            u'Antivol trottinette \xe9lectrique',
        'frein':              u'Pi\xe8ce frein trottinette \xe9lectrique',
        'piece_electronique': u'Pi\xe8ce d\xe9tach\xe9e trottinette \xe9lectrique',
        'piece_detachee':     u'Pi\xe8ce d\xe9tach\xe9e trottinette \xe9lectrique',
        'accessoire':         u'Accessoire trottinette \xe9lectrique',
        'equipement':         u'\xc9quipement mobilit\xe9 \xe9lectrique',
        'velo':               u'V\xe9lo \xe9lectrique',
    }.get(ptype, u'Accessoire trottinette \xe9lectrique')

    if any(vb in raw_title.lower() for vb in VELO_BRANDS):
        type_suffix = type_suffix.replace(
            u'trottinette \xe9lectrique', u'v\xe9lo \xe9lectrique'
        )

    if 'trottinette' in raw_title.lower() or 'compatible' in raw_title.lower():
        title = raw_title
    elif brand and brand.lower() not in raw_title.lower() and brand != 'Freemoov':
        title = u'%s %s - %s' % (brand, raw_title, type_suffix)
    else:
        title = u'%s - %s' % (raw_title, type_suffix)
    return title[:150].strip(u' -\u2013')


# ─────────────────────────────────────────────────────────────────────
# Description builder — max 5000 chars
# ─────────────────────────────────────────────────────────────────────

def _build_variant_block(product):
    """Build a text block listing price-different variants for the description."""
    variants = product.product_variant_ids
    if not variants or len(variants) <= 1:
        return ''

    base_price = product.list_price
    entries = []
    for v in variants:
        extra = sum(v.product_template_attribute_value_ids.mapped('price_extra'))
        final_price = base_price + extra
        attrs = [a.name for a in v.product_template_attribute_value_ids]
        if not attrs:
            continue
        label = ' / '.join(attrs)
        entries.append((label, final_price))

    prices = set(p for _, p in entries)
    if len(prices) <= 1:
        return ''

    lines = [u'Configurations disponibles :']
    for label, price in sorted(entries, key=lambda x: x[1]):
        lines.append(u'- %s : %.2f \u20ac' % (label, price))
    return ' '.join(lines)


def build_description(product, brand, ptype, raw_summary, raw_desc_sale):
    """Build cleaned, SEO-enriched description (max 5000 chars)."""
    raw = raw_summary or raw_desc_sale or ''
    clean = clean_description(raw)
    product_name = _get_fr(product.name) or ''

    type_fr = {
        'trottinette':        u'trottinette \xe9lectrique',
        'pneu':               u'pneu pour trottinette \xe9lectrique',
        'chambre_air':        u'chambre \xe0 air pour trottinette \xe9lectrique',
        'casque':             u'casque pour la mobilit\xe9 \xe9lectrique',
        'gant':               u'gants pour la mobilit\xe9 \xe9lectrique',
        'chargeur':           u'chargeur pour trottinette \xe9lectrique',
        'antivol':            u'antivol pour trottinette \xe9lectrique',
        'frein':              u'pi\xe8ce de frein pour trottinette \xe9lectrique',
        'piece_electronique': u'pi\xe8ce \xe9lectronique pour trottinette',
        'piece_detachee':     u'pi\xe8ce d\xe9tach\xe9e pour trottinette \xe9lectrique',
        'accessoire':         u'accessoire pour trottinette \xe9lectrique',
        'equipement':         u'\xe9quipement pour la mobilit\xe9 \xe9lectrique',
        'velo':               u'v\xe9lo \xe9lectrique',
    }.get(ptype, u'accessoire pour trottinette \xe9lectrique')

    if len(clean) < 50:
        clean = u'%s, %s compatible avec de nombreux mod\xe8les de trottinettes \xe9lectriques.' % (
            product_name, type_fr
        )
        if brand and brand != 'Freemoov':
            clean += u' Marque : %s.' % brand

    if product_name and not clean.lower().startswith(product_name.lower()[:20]):
        clean = u'%s. %s' % (product_name, clean)

    clean = re.sub(r'\s+', ' ', clean).strip()
    if clean and clean[-1] not in '.!?':
        clean += '.'

    if ptype == 'velo' and '25 km' not in clean.lower():
        clean = clean.rstrip('.')
        clean += u'. Vitesse maximale assist\xe9e : 25 km/h. Conforme \xe0 la r\xe9glementation europ\xe9enne EN 15194.'

    variant_block = _build_variant_block(product)
    if variant_block:
        clean = clean.rstrip('.') + '. ' + variant_block

    return clean[:5000].strip()


# ─────────────────────────────────────────────────────────────────────
# Shipping
# ─────────────────────────────────────────────────────────────────────

def compute_shipping(country, weight, price_ttc):
    """Compute shipping cost for a country based on weight and price."""
    if price_ttc >= FREE_SHIPPING_THRESHOLD:
        return 0.0
    rates = SHIPPING_RATES.get(country, SHIPPING_RATES['BE'])
    if weight and weight >= 30:
        return rates['heavy']
    return rates['standard']


def estimate_weight(ptype, price_ttc=0):
    """Estimate weight when not set in Odoo, based on product type."""
    if ptype == 'trottinette':
        if price_ttc >= 3000:
            return 40.0
        if price_ttc >= 1500:
            return 25.0
        if price_ttc >= 800:
            return 18.0
        return 14.0
    if ptype == 'velo':
        if price_ttc >= 3000:
            return 35.0
        if price_ttc >= 1500:
            return 28.0
        return 22.0
    weights = {
        'pneu': 0.8, 'chambre_air': 0.8, 'casque': 0.6, 'chargeur': 1.2,
        'antivol': 1.5, 'frein': 0.3, 'piece_electronique': 0.5,
        'piece_detachee': 0.5, 'gant': 0.2, 'equipement': 0.4,
    }
    return weights.get(ptype, 0.5)


def price_label(price_ttc):
    """Custom label 0: price range."""
    if price_ttc >= 3000:
        return 'Premium (3000+)'
    if price_ttc >= 1500:
        return 'Haut de gamme (1500-3000)'
    if price_ttc >= 500:
        return 'Milieu de gamme (500-1500)'
    if price_ttc >= 100:
        return u'Entr\xe9e de gamme (100-500)'
    return 'Petit budget (0-100)'


# ─────────────────────────────────────────────────────────────────────
# Scope filter
# ─────────────────────────────────────────────────────────────────────

def is_in_feed_scope(product):
    """Check if a product should be included in the GMC feed."""
    title = (_get_fr(product.name) or '').lower()
    cats = []
    if product.public_categ_ids:
        cats = [(_get_fr(c.name) or '').lower() for c in product.public_categ_ids]
    all_text = title + ' ' + ' '.join(cats)
    return not any(kw in all_text for kw in EXCLUDE_KEYWORDS)


# ═════════════════════════════════════════════════════════════════════
# Main entry point: prepare_product_data
# Called by _prepare_gmc_product_input() on product.template
# ═════════════════════════════════════════════════════════════════════

def prepare_product_data(product, base_url='https://www.freemoov.com',
                         content_language='fr', feed_label='BE'):
    """
    Build complete GMC product data dict from an Odoo product.template record.
    The product should be called with lang='fr_BE' context.
    Returns a dict ready for GoogleMerchantService.insert_product().
    """
    product_ctx = product.with_context(lang='fr_BE')
    raw_title = _get_fr(product_ctx.name) or ''
    title_lower = raw_title.lower()
    cat_names = _get_cat_names(product_ctx)

    brand = 'Freemoov'
    if hasattr(product_ctx, 'brand_id') and product_ctx.brand_id and product_ctx.brand_id.name:
        brand = product_ctx.brand_id.name

    ptype = detect_type(title_lower, cat_names)
    gpc_id = GPC_MAP.get(ptype, GPC_MAP.get('trottinette', 5879))
    product_type = PRODUCT_TYPE_MAP.get(ptype, PRODUCT_TYPE_MAP.get('accessoire', ''))

    opt_title = build_title(product_ctx, brand, raw_title, ptype)
    raw_summary = _get_fr(getattr(product_ctx, 'summary', None) or '')
    raw_desc_sale = _get_fr(product_ctx.description_sale or '')
    opt_desc = build_description(product_ctx, brand, ptype, raw_summary, raw_desc_sale)

    # Price — list_price is already TTC (Belgian VAT price_include=True)
    price_ttc = float(product_ctx.list_price or 0)
    sale_price_ttc = None

    # For multi-variant products with different prices, use the lowest variant price
    variants = product_ctx.product_variant_ids
    if variants and len(variants) > 1:
        variant_prices = []
        for v in variants:
            extra = sum(v.product_template_attribute_value_ids.mapped('price_extra'))
            variant_prices.append(price_ttc + extra)
        if len(set(round(p, 2) for p in variant_prices)) > 1:
            price_ttc = min(variant_prices)

    if (hasattr(product_ctx, 'compare_list_price')
            and product_ctx.compare_list_price
            and product_ctx.compare_list_price > price_ttc):
        sale_price_ttc = price_ttc
        price_ttc = float(product_ctx.compare_list_price)

    price_micros = int(round(price_ttc * 1_000_000))
    sale_price_micros = int(round(sale_price_ttc * 1_000_000)) if sale_price_ttc else None

    # Variant info
    barcode = ''
    default_code = ''
    if variants and len(variants) == 1:
        v = variants[0]
        barcode = (v.barcode or '').strip()
        default_code = (v.default_code or '').strip()

    # Priority: gmc_offer_id override > default_code > Odoo ID
    if hasattr(product_ctx, 'gmc_offer_id') and product_ctx.gmc_offer_id:
        offer_id = product_ctx.gmc_offer_id.strip()[:50]
    else:
        offer_id = (default_code or str(product_ctx.id))[:50]

    has_gtin = bool(barcode)
    has_mpn = bool(default_code)
    identifier_exists = bool(has_gtin or (has_mpn and brand))

    # Link
    path = getattr(product_ctx, 'website_url', None) or ('/shop/product/%s' % product_ctx.id)
    link = base_url + path if path.startswith('/') else path

    # Images
    image_link = '%s/web/image/product.template/%s/image_1920' % (base_url, product_ctx.id)
    additional_image_links = []
    if hasattr(product_ctx, 'product_template_image_ids') and product_ctx.product_template_image_ids:
        for img in product_ctx.product_template_image_ids[:10]:
            additional_image_links.append(
                '%s/web/image/product.image/%s/image_1920' % (base_url, img.id)
            )

    # Availability
    availability = 'IN_STOCK'
    try:
        availability = product_ctx._get_gmc_availability()
    except Exception:
        pass

    # availability_date for preorder/backorder
    availability_date = ''
    av_lower = availability.lower().replace(' ', '_')
    if av_lower == 'preorder':
        availability_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S+01:00')
    elif av_lower == 'backorder':
        availability_date = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%S+01:00')

    condition = product_ctx.gmc_condition or 'new'

    # Weight
    weight = product_ctx.weight if product_ctx.weight else None
    effective_weight = weight if weight else estimate_weight(ptype, price_ttc)

    # Shipping per country
    shipping = []
    for country in ('BE', 'FR', 'LU', 'NL'):
        cost = compute_shipping(country, effective_weight, price_ttc)
        shipping.append({
            'country': country,
            'price_micros': int(round(cost * 1_000_000)),
            'currency_code': 'EUR',
        })

    # Custom labels
    cl0 = price_label(price_ttc)
    cl1 = brand[:100]
    cl2 = product_type.split(' > ')[1] if ' > ' in product_type else product_type
    cl3 = 'Avec GTIN' if has_gtin else 'Sans GTIN'
    cl4 = 'Images multiples' if additional_image_links else 'Image unique'

    return {
        'offer_id': offer_id,
        'content_language': content_language,
        'feed_label': feed_label,
        'title': opt_title,
        'description': opt_desc,
        'link': link,
        'image_link': image_link,
        'additional_image_links': additional_image_links,
        'availability': availability,
        'availability_date': availability_date,
        'condition': condition,
        'google_product_category': str(gpc_id),
        'product_type': product_type,
        'brand': brand[:70],
        'gtin': barcode,
        'mpn': (default_code or offer_id)[:70],
        'identifier_exists': identifier_exists,
        'price_micros': price_micros,
        'sale_price_micros': sale_price_micros,
        'currency_code': 'EUR',
        'shipping_weight_value': effective_weight,
        'shipping_weight_unit': 'kg',
        'shipping': shipping,
        'free_shipping_threshold': FREE_SHIPPING_THRESHOLD,
        'ships_from_country': 'BE',
        'custom_label_0': cl0[:100],
        'custom_label_1': cl1[:100],
        'custom_label_2': cl2[:100],
        'custom_label_3': cl3[:100],
        'custom_label_4': cl4[:100],
    }
