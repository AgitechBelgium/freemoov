# -*- coding: utf-8 -*-
import json
import logging
import re
from datetime import timedelta
from urllib.parse import urlparse

from markupsafe import Markup

from odoo import fields, models, api
from odoo.addons.http_routing.models.ir_http import slug
from odoo.http import request
from odoo.tools import html2plaintext
from odoo.tools.translate import html_translate

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Technical hosts that must never leak into canonical tags or structured data.
# Odoo.sh serves <db>.odoo.com with a hardcoded "Disallow: /" robots.txt, so
# any URL we emit on that host points Google at something it may not crawl.
# ---------------------------------------------------------------------------
TECHNICAL_HOST_MARKERS = ('.odoo.com', '.odoo.sh', 'localhost', '127.0.0.1')


def is_technical_host(url):
    """Return True if `url` sits on a host that must not be published."""
    if not url:
        return True
    host = urlparse(url if '://' in url else 'https://' + url).netloc.lower()
    return any(marker in host for marker in TECHNICAL_HOST_MARKERS)


def seo_base_url(env):
    """Public base URL for every SEO artefact (canonical, hreflang, JSON-LD).

    `website.get_base_url()` falls back to the `web.base.url` system parameter,
    which on Odoo.sh holds the technical <db>.odoo.com host. Emitting it makes
    the whole site declare a reference URL that is blocked by robots.txt.
    """
    return env['website'].get_current_website()._seo_base_url()


# ---------------------------------------------------------------------------
# Shipping & return constants (aligned with GMC module)
# ---------------------------------------------------------------------------
SHIPPING_RATES = {
    'BE': {'rate': 0.00, 'transit_min': 2, 'transit_max': 5},
    'FR': {'rate': 19.90, 'transit_min': 3, 'transit_max': 7},
    'LU': {'rate': 14.90, 'transit_min': 2, 'transit_max': 5},
    'NL': {'rate': 19.90, 'transit_min': 3, 'transit_max': 7},
}
HANDLING_DAYS_MIN = 0
HANDLING_DAYS_MAX = 2
RETURN_DAYS = 14


class IrHttpSeo(models.AbstractModel):
    """301-redirect archived product pages to their parent category."""
    _inherit = 'ir.http'

    @classmethod
    def _serve_fallback(cls):
        # Intercept 404 on /shop/<slug>-<id> for archived products
        if request and request.httprequest.path.startswith('/shop/'):
            match = re.search(r'-(\d+)$', request.httprequest.path)
            if match:
                product_id = int(match.group(1))
                product = request.env['product.template'].sudo().with_context(
                    active_test=False,
                ).browse(product_id)
                if product.exists() and not product.active:
                    categ = product.public_categ_ids[:1]
                    url = '/shop/category/%s' % slug(categ) if categ else '/shop'
                    return request.redirect(url, code=301)
        return super()._serve_fallback()


class SeoMetadataFix(models.AbstractModel):
    """Rewrite Open Graph / Twitter URLs that Odoo built on the technical host."""
    _inherit = 'website.seo.metadata'

    def _default_website_meta(self):
        res = super()._default_website_meta()
        if not request:
            return res

        # Store pages were built in the website editor and carry no meta
        # description. Supply one as a default — anything typed in the SEO
        # panel still wins, since website.layout reads the stored value first.
        store_desc = request.website.get_store_meta_description(request.httprequest.path)
        if store_desc and not res.get('default_meta_description'):
            res['default_meta_description'] = store_desc
            res['default_opengraph'].setdefault('og:description', store_desc)
            res['default_twitter'].setdefault('twitter:description', store_desc)
        return res

    def get_website_meta(self):
        meta = super().get_website_meta()
        if not request:
            return meta
        domain = request.website._seo_base_url()
        if is_technical_host(domain):
            return meta

        for bucket in ('opengraph_meta', 'twitter_meta'):
            data = meta.get(bucket, {})
            for key in list(data.keys()):
                val = data[key]
                if isinstance(val, str) and '://' in val and is_technical_host(val):
                    parsed = urlparse(val)
                    data[key] = domain + parsed.path
                    if parsed.query:
                        data[key] += '?' + parsed.query
        return meta


class ProductTemplateSeo(models.Model):
    _inherit = 'product.template'

    # ------------------------------------------------------------------
    # SEO fields
    # ------------------------------------------------------------------
    faq_ids = fields.One2many(
        'product.faq', 'product_id', string='FAQ',
    )
    editorial_review = fields.Html(
        string='Avis expert', translate=html_translate,
        sanitize_attributes=False,
    )
    video_url = fields.Char(string='URL Vidéo')

    # ------------------------------------------------------------------
    # Meta tags (title + description auto-generation)
    # ------------------------------------------------------------------

    _SEO_PRIORITY_ATTRS = ['Autonomie', 'Puissance moteur', 'Vitesse', 'Poids']

    def _build_auto_meta_title(self):
        """Build a meta title, enriching short names with category."""
        name = self.name or ''
        base = '%s | Freemoov' % name
        if len(base) < 40 and self.public_categ_ids:
            categ = self.public_categ_ids[0].name or ''
            base = '%s \u2014 %s | Freemoov' % (name, categ)
        return base

    def _default_website_meta(self):
        res = super()._default_website_meta()
        if not self.website_meta_title:
            title = self._build_auto_meta_title()
            res['default_opengraph']['og:title'] = title
            res['default_twitter']['twitter:title'] = title
        if not self.website_meta_description:
            desc = self._build_auto_meta_description()
            res['default_meta_description'] = desc
            res['default_opengraph']['og:description'] = desc
            res['default_twitter']['twitter:description'] = desc
        return res

    def _build_auto_meta_description(self):
        """Build a meta description from product name, brand and key attributes."""
        self.ensure_one()
        real_brand = hasattr(self, 'x_studio_marque') and self.x_studio_marque
        brand = real_brand or ''
        name = self.name or ''

        specs = []
        for line in self.attribute_line_ids:
            attr_name = line.attribute_id.name
            if attr_name in self._SEO_PRIORITY_ATTRS:
                values = line.value_ids.mapped('name')
                if not values:
                    continue
                if len(values) == 1:
                    specs.append('%s %s' % (attr_name, values[0]))
                else:
                    # Multi-value = variant axis → show range
                    specs.append('%s de %s à %s' % (attr_name, values[0], values[-1]))

        specs.sort(key=lambda s: next(
            (i for i, a in enumerate(self._SEO_PRIORITY_ATTRS) if s.startswith(a)), 99
        ))

        # Only append brand/category if not already in product name
        def _normalize(s):
            return set(w.rstrip('s') for w in s.lower().split() if len(w) > 2)
        name_norm = _normalize(name)
        brand_extra = brand if brand and not _normalize(brand).issubset(name_norm) else ''

        if specs:
            prefix = ('%s %s' % (name, brand_extra)).strip()
            desc = '%s : %s. Livraison gratuite en Belgique.' % (prefix, ', '.join(specs))
        else:
            categ = self._seo_category_name()
            categ_extra = categ if categ and not _normalize(categ).issubset(name_norm) else ''
            prefix = ('%s %s' % (name, brand_extra)).strip()
            if categ_extra:
                desc = '%s \u2014 %s disponible chez Freemoov. Livraison gratuite en Belgique.' % (prefix, categ_extra)
            else:
                desc = '%s \u2014 disponible chez Freemoov. Livraison gratuite en Belgique.' % prefix

        if len(desc) > 160:
            desc = desc[:157] + '...'
        return desc

    # ------------------------------------------------------------------
    # JSON-LD helpers
    # ------------------------------------------------------------------

    def _get_brand_name(self):
        if hasattr(self, 'x_studio_marque') and self.x_studio_marque:
            return self.x_studio_marque
        return 'Freemoov'

    def _seo_availability(self):
        """Schema.org availability URL based on stock status."""
        try:
            website = self.env['website'].get_current_website()
            stock = self.get_stock_availability(website=website)
            if stock.get('qty_avail', 0) > 0 or stock.get('is_dropship') or stock.get('allow_out_of_stock'):
                return 'https://schema.org/InStock'
        except Exception:
            pass
        return 'https://schema.org/OutOfStock'

    def _seo_shipping_details(self):
        details = []
        for country, info in SHIPPING_RATES.items():
            details.append({
                '@type': 'OfferShippingDetails',
                'shippingDestination': {
                    '@type': 'DefinedRegion',
                    'addressCountry': country,
                },
                'shippingRate': {
                    '@type': 'MonetaryAmount',
                    'value': info['rate'],
                    'currency': 'EUR',
                },
                'deliveryTime': {
                    '@type': 'ShippingDeliveryTime',
                    'handlingTime': {
                        '@type': 'QuantitativeValue',
                        'minValue': HANDLING_DAYS_MIN,
                        'maxValue': HANDLING_DAYS_MAX,
                        'unitCode': 'DAY',
                    },
                    'transitTime': {
                        '@type': 'QuantitativeValue',
                        'minValue': info['transit_min'],
                        'maxValue': info['transit_max'],
                        'unitCode': 'DAY',
                    },
                },
            })
        return details

    @staticmethod
    def _seo_return_policy():
        return {
            '@type': 'MerchantReturnPolicy',
            'applicableCountry': list(SHIPPING_RATES.keys()),
            'returnPolicyCategory': 'https://schema.org/MerchantReturnFiniteReturnWindow',
            'merchantReturnDays': RETURN_DAYS,
            'returnMethod': [
                'https://schema.org/ReturnByMail',
                'https://schema.org/ReturnInStore',
            ],
            'returnFees': 'https://schema.org/ReturnFeesCustomerResponsibility',
        }

    # Real Google Business reviews from Freemoov Liège & Namur
    _STORE_REVIEWS = [
        {
            '@type': 'Review',
            'author': {'@type': 'Person', 'name': 'Anthony Fockenoy'},
            'datePublished': '2026-02-10',
            'reviewBody': 'Merci pour l\'accompagnement, très bonne expérience. '
                          'Équipe au top, je recommande vivement Freemoov.',
            'reviewRating': {
                '@type': 'Rating', 'ratingValue': 5, 'bestRating': 5,
            },
        },
        {
            '@type': 'Review',
            'author': {'@type': 'Person', 'name': 'Kevin Radogewski'},
            'datePublished': '2026-02-25',
            'reviewBody': 'Super service, livraison rapide et équipe '
                          'disponible pour les conseils. Trottinette top !',
            'reviewRating': {
                '@type': 'Rating', 'ratingValue': 5, 'bestRating': 5,
            },
        },
        {
            '@type': 'Review',
            'author': {'@type': 'Person', 'name': 'Daniel Chantriaux'},
            'datePublished': '2026-02-12',
            'reviewBody': 'Communication excellente, équipe au top, bon suivi '
                          'par mail et WhatsApp. À l\'écoute et réactif.',
            'reviewRating': {
                '@type': 'Rating', 'ratingValue': 5, 'bestRating': 5,
            },
        },
    ]

    @staticmethod
    def _seo_store_reviews():
        return ProductTemplateSeo._STORE_REVIEWS

    def _seo_images(self):
        """Return list of all product image URLs (main + extras)."""
        website = self.env['website'].get_current_website()
        base_url = website._seo_base_url()
        images = [base_url + website.image_url(self, 'image_1920')]
        for img in self.product_template_image_ids:
            images.append('%s/web/image/product.image/%s/image_1920' % (base_url, img.id))
        return images

    @staticmethod
    def _clean_plaintext(text):
        """Remove markdown/image artifacts from html2plaintext output."""
        # Remove markdown bold/italic: **text**, ***text***, ***/text/***
        text = re.sub(r'\*{2,3}/|/\*{2,3}', '', text)
        text = re.sub(r'\*{2,3}', '', text)
        # Remove image alt text references: Logo-Brand [1], Image [5], [N]
        text = re.sub(r'[\w-]+ \[\d+\]', '', text)
        text = re.sub(r'\[\d+\]', '', text)
        # Collapse multiple newlines/spaces
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'  +', ' ', text)
        return text.strip()

    def _seo_description(self):
        """Return best available text description (summary > description_sale > name)."""
        if self.summary:
            text = html2plaintext(self.summary)
            text = self._clean_plaintext(text)
            return text[:1000].strip()
        if self.description_sale:
            return self.description_sale[:1000].strip()
        return self.name

    def _seo_category_name(self):
        categ = self.public_categ_ids[:1]
        return categ.name if categ else ''

    def _seo_variant_label(self, variant):
        """Return the distinguishing label of a variant (e.g. 'Noir')."""
        labels = []
        for ptav in variant.product_template_attribute_value_ids:
            line = ptav.attribute_line_id
            if len(line.product_template_value_ids) > 1:
                labels.append(ptav.name)
        return ' / '.join(labels) if labels else ''

    def _seo_variant_offer(self, variant):
        """Return an Offer dict for a specific product variant."""
        base_url = seo_base_url(self.env)
        offer = {
            '@type': 'Offer',
            'url': base_url + self.website_url,
            'priceCurrency': 'EUR',
            'price': '%.2f' % (self.list_price + variant.price_extra),
            'priceValidUntil': (fields.Date.today() + timedelta(days=90)).isoformat(),
            'availability': self._seo_availability(),
            'itemCondition': 'https://schema.org/NewCondition',
            'seller': {'@type': 'Organization', 'name': 'Freemoov'},
            'shippingDetails': self._seo_shipping_details(),
            'hasMerchantReturnPolicy': self._seo_return_policy(),
        }
        sku = variant.default_code or self.default_code or ''
        if sku:
            offer['sku'] = sku
        return offer

    def _seo_aggregate_rating(self):
        """Return aggregateRating dict (per-product or store-wide fallback)."""
        if hasattr(self, 'rating_count') and self.rating_count and self.rating_count > 0:
            return {
                '@type': 'AggregateRating',
                'ratingValue': '%.1f' % self.rating_avg,
                'reviewCount': self.rating_count,
                'bestRating': 5,
                'worstRating': 1,
            }
        return {
            '@type': 'AggregateRating',
            'ratingValue': '4.8',
            'reviewCount': 350,
            'bestRating': 5,
            'worstRating': 1,
        }

    def _get_jsonld_product(self):
        """Return Markup-safe JSON-LD string for a Product/ProductGroup schema."""
        self.ensure_one()
        base_url = seo_base_url(self.env)
        variants = self.product_variant_ids.filtered('active')
        is_group = len(variants) > 1

        # Common fields shared by both Product and ProductGroup
        data = {
            '@context': 'https://schema.org',
            '@type': 'ProductGroup' if is_group else 'Product',
            'name': self.name,
            'description': self._seo_description(),
            'url': base_url + self.website_url,
            'image': self._seo_images(),
            'brand': {
                '@type': 'Brand',
                'name': self._get_brand_name(),
            },
            'aggregateRating': self._seo_aggregate_rating(),
            'review': self._seo_store_reviews(),
        }

        categ = self._seo_category_name()
        if categ:
            data['category'] = categ

        if self.weight:
            data['weight'] = {
                '@type': 'QuantitativeValue',
                'value': self.weight,
                'unitCode': 'KGM',
            }

        if is_group:
            # ProductGroup: each variant is a Product with its own Offer
            data['productGroupID'] = str(self.id)
            # AggregateOffer at ProductGroup level (required by Google)
            prices = [(self.list_price + v.price_extra) for v in variants]
            data['offers'] = {
                '@type': 'AggregateOffer',
                'lowPrice': '%.2f' % min(prices),
                'highPrice': '%.2f' % max(prices),
                'priceCurrency': 'EUR',
                'offerCount': len(variants),
                'availability': self._seo_availability(),
            }
            agg_rating = self._seo_aggregate_rating()
            variant_list = []
            for variant in variants:
                label = self._seo_variant_label(variant)
                v_name = '%s - %s' % (self.name, label) if label else self.name
                v_data = {
                    '@type': 'Product',
                    'name': v_name,
                    'url': base_url + self.website_url,
                    'image': data['image'][0] if data['image'] else '',
                    'offers': self._seo_variant_offer(variant),
                    'aggregateRating': agg_rating,
                }
                if variant.default_code:
                    v_data['sku'] = variant.default_code
                if variant.barcode:
                    v_data['gtin13'] = variant.barcode
                variant_list.append(v_data)
            data['hasVariant'] = variant_list
        else:
            # Single Product: one Offer, SKU/GTIN at product level
            variant = variants[:1]
            data['offers'] = {
                '@type': 'Offer',
                'url': base_url + self.website_url,
                'priceCurrency': 'EUR',
                'price': '%.2f' % self.list_price,
                'priceValidUntil': (fields.Date.today() + timedelta(days=90)).isoformat(),
                'availability': self._seo_availability(),
                'itemCondition': 'https://schema.org/NewCondition',
                'seller': {'@type': 'Organization', 'name': 'Freemoov'},
                'shippingDetails': self._seo_shipping_details(),
                'hasMerchantReturnPolicy': self._seo_return_policy(),
            }
            sku = (variant.default_code if variant else '') or self.default_code or ''
            if sku:
                data['sku'] = sku
            barcode = variant.barcode if variant else ''
            if barcode:
                data['gtin13'] = barcode

        return Markup(json.dumps(data, ensure_ascii=False))

    def _get_jsonld_faq(self):
        """Return FAQPage JSON-LD from product.faq records."""
        self.ensure_one()
        if not self.faq_ids:
            return ''
        entities = []
        for faq in self.faq_ids.sorted('sequence'):
            answer_text = html2plaintext(faq.answer or '')
            entities.append({
                '@type': 'Question',
                'name': faq.question,
                'acceptedAnswer': {
                    '@type': 'Answer',
                    'text': answer_text,
                },
            })
        data = {
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            'mainEntity': entities,
        }
        return Markup(json.dumps(data, ensure_ascii=False))

    def _get_jsonld_video(self):
        """Return VideoObject JSON-LD if product has a video_url."""
        self.ensure_one()
        if not self.video_url:
            return ''
        base_url = seo_base_url(self.env)
        data = {
            '@context': 'https://schema.org',
            '@type': 'VideoObject',
            'name': '%s — Freemoov' % self.name,
            'description': self.description_sale or self.name,
            'thumbnailUrl': base_url + self.env['website'].get_current_website().image_url(self, 'image_512'),
            'uploadDate': (self.write_date or fields.Datetime.now()).isoformat(),
            'contentUrl': self.video_url,
        }
        # Try to extract embed URL for embedUrl
        embed = self._get_video_embed_url()
        if embed:
            data['embedUrl'] = embed
        return Markup(json.dumps(data, ensure_ascii=False))

    def _get_video_embed_url(self):
        """Parse video URL and return embeddable URL."""
        url = self.video_url or ''
        # YouTube
        yt_match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)', url)
        if yt_match:
            return 'https://www.youtube.com/embed/%s' % yt_match.group(1)
        # Instagram reel
        ig_match = re.search(r'instagram\.com/reel/([\w-]+)', url)
        if ig_match:
            return 'https://www.instagram.com/reel/%s/embed/' % ig_match.group(1)
        # TikTok
        tt_match = re.search(r'tiktok\.com/@[\w.]+/video/(\d+)', url)
        if tt_match:
            return 'https://www.tiktok.com/embed/v2/%s' % tt_match.group(1)
        return ''

    def _get_jsonld_breadcrumb(self, category=None):
        """Return JSON-LD BreadcrumbList for a product page."""
        self.ensure_one()
        base_url = seo_base_url(self.env)
        items = [
            {'@type': 'ListItem', 'position': 1, 'name': 'Accueil', 'item': base_url + '/'},
        ]
        if category:
            items.append({
                '@type': 'ListItem', 'position': 2,
                'name': category.name,
                'item': base_url + '/shop/category/%s' % slug(category),
            })
            items.append({
                '@type': 'ListItem', 'position': 3, 'name': self.name,
            })
        else:
            items.append({
                '@type': 'ListItem', 'position': 2, 'name': 'Produits',
                'item': base_url + '/shop',
            })
            items.append({
                '@type': 'ListItem', 'position': 3, 'name': self.name,
            })
        data = {
            '@context': 'https://schema.org',
            '@type': 'BreadcrumbList',
            'itemListElement': items,
        }
        return Markup(json.dumps(data, ensure_ascii=False))


class ProductPublicCategorySeo(models.Model):
    _inherit = 'product.public.category'

    seo_intro = fields.Html(
        string='Introduction SEO', translate=html_translate,
        sanitize_attributes=False,
    )
    blog_id = fields.Many2one(
        'blog.blog', string='Blog associé',
    )
    seo_noindex = fields.Boolean(
        string='Exclure de l\'index Google',
        help="Pour les catégories qui ne servent qu'à la navigation "
             "(« Nos marques de… », « Par type »…). Elles se placent sur les "
             "mêmes requêtes que la catégorie principale et lui font "
             "concurrence. La page reste visible et ses liens sont suivis, "
             "elle n'apparaît simplement plus dans les résultats de recherche.",
    )

    def _default_website_meta(self):
        res = super()._default_website_meta()
        if not self.website_meta_title:
            title = '%s | Freemoov' % self.name
            res['default_opengraph']['og:title'] = title
            res['default_twitter']['twitter:title'] = title
        if not self.website_meta_description:
            desc = self.category_description[:160] if self.category_description else (
                'Découvrez notre sélection de %s chez Freemoov. '
                'Livraison gratuite en Belgique, SAV expert à Liège et Namur.'
            ) % self.name.lower()
            res['default_meta_description'] = desc
            res['default_opengraph']['og:description'] = desc
            res['default_twitter']['twitter:description'] = desc
        return res

    def _get_jsonld_breadcrumb(self):
        """Return JSON-LD BreadcrumbList for a category page."""
        self.ensure_one()
        base_url = seo_base_url(self.env)
        items = [
            {'@type': 'ListItem', 'position': 1, 'name': 'Accueil', 'item': base_url + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Produits', 'item': base_url + '/shop'},
        ]
        pos = 3
        for parent in reversed(self.parents_and_self[:-1]):
            items.append({
                '@type': 'ListItem', 'position': pos,
                'name': parent.name,
                'item': base_url + '/shop/category/%s' % slug(parent),
            })
            pos += 1
        items.append({'@type': 'ListItem', 'position': pos, 'name': self.name})
        data = {
            '@context': 'https://schema.org',
            '@type': 'BreadcrumbList',
            'itemListElement': items,
        }
        return Markup(json.dumps(data, ensure_ascii=False))

    def _get_jsonld_collection(self, products):
        """Return JSON-LD CollectionPage + ItemList for a category listing."""
        self.ensure_one()
        base_url = seo_base_url(self.env)
        website = self.env['website'].get_current_website()
        price_valid = (fields.Date.today() + timedelta(days=90)).isoformat()
        list_items = []
        shipping = products[:1]._seo_shipping_details() if products else []
        return_policy = ProductTemplateSeo._seo_return_policy()
        store_reviews = ProductTemplateSeo._seo_store_reviews()
        for idx, product in enumerate(products[:36], start=1):
            item = {
                '@type': 'Product',
                'name': product.name,
                'url': base_url + product.website_url,
                'image': base_url + website.image_url(product, 'image_512'),
                'description': product._seo_description(),
                'brand': {
                    '@type': 'Brand',
                    'name': product._get_brand_name(),
                },
                'offers': {
                    '@type': 'Offer',
                    'url': base_url + product.website_url,
                    'price': '%.2f' % product.list_price,
                    'priceCurrency': 'EUR',
                    'priceValidUntil': price_valid,
                    'availability': product._seo_availability(),
                    'itemCondition': 'https://schema.org/NewCondition',
                    'seller': {'@type': 'Organization', 'name': 'Freemoov'},
                    'shippingDetails': shipping,
                    'hasMerchantReturnPolicy': return_policy,
                },
                'aggregateRating': product._seo_aggregate_rating(),
                'review': store_reviews,
            }
            sku = product.default_code or ''
            if sku:
                item['sku'] = sku
            list_items.append({
                '@type': 'ListItem',
                'position': idx,
                'item': item,
            })
        data = {
            '@context': 'https://schema.org',
            '@type': 'CollectionPage',
            'name': self.name,
            'url': base_url + '/shop/category/%s' % slug(self),
            'mainEntity': {
                '@type': 'ItemList',
                'numberOfItems': len(list_items),
                'itemListElement': list_items,
            },
        }
        return Markup(json.dumps(data, ensure_ascii=False))


class WebsiteSeo(models.Model):
    _inherit = 'website'

    # Force 24 products per page (performance fix for mono-thread)
    shop_ppg = fields.Integer(default=24)

    # ------------------------------------------------------------------
    # Sitemap: exclude technical URLs
    # ------------------------------------------------------------------
    _SITEMAP_EXCLUDE = (
        '/livechat', '/helpdesk', '/slider_s', '/website/info',
        '/my/', '/web/login', '/web/signup', '/web/reset_password',
        '/shop/cart', '/shop/checkout', '/shop/payment', '/shop/confirm_order',
        # Application forms duplicate the job pages, and the profile/slides
        # routes come from modules Freemoov does not use publicly.
        '/jobs/apply', '/profile/', '/slides',
    )

    def _enumerate_pages(self, query_string=None, force=False):
        for page in super()._enumerate_pages(query_string=query_string, force=force):
            loc = page.get('loc', '')
            if any(excl in loc for excl in self._SITEMAP_EXCLUDE):
                continue
            yield page

    # ------------------------------------------------------------------
    # Public base URL
    # ------------------------------------------------------------------
    def _seo_base_url(self):
        """Return the domain we want search engines to index.

        Resolution order:
          1. the website's configured `domain` (the value an admin controls),
          2. the host actually serving the current request,
          3. the native `get_base_url()`, as a last resort.

        Steps 1 and 2 are skipped when they resolve to a technical host, so a
        misconfigured `web.base.url` can no longer poison canonical tags,
        hreflang or JSON-LD. This is a safety net, not the fix: `website.domain`
        should still be set to https://www.freemoov.com in production.
        """
        domain = (self.domain or '').strip().rstrip('/')
        if domain and not is_technical_host(domain):
            return domain if domain.startswith('http') else 'https://' + domain

        if request:
            host = request.httprequest.host_url.rstrip('/')
            if not is_technical_host(host):
                return host

        return self.get_base_url().rstrip('/')

    # ------------------------------------------------------------------
    # Canonical: public domain + fix / vs /home
    # ------------------------------------------------------------------
    def _get_canonical_url(self, canonical_params=None):
        canonical = super()._get_canonical_url(canonical_params=canonical_params)
        base_url = self._seo_base_url()

        # Native canonical is built on get_base_url(); re-anchor it on the
        # public domain so we never advertise the technical host.
        if is_technical_host(canonical) and not is_technical_host(base_url):
            parsed = urlparse(canonical)
            canonical = base_url + parsed.path
            if parsed.query:
                canonical += '?' + parsed.query

        if canonical.rstrip('/') == base_url + '/home':
            return base_url + '/'
        return canonical

    # ------------------------------------------------------------------
    # Organization JSON-LD (homepage only)
    # ------------------------------------------------------------------
    def get_jsonld_organization(self):
        base_url = self._seo_base_url()
        data = {
            '@context': 'https://schema.org',
            '@type': 'OnlineStore',
            '@id': base_url + '/#organization',
            'name': 'Freemoov',
            'url': base_url,
            'logo': {
                '@type': 'ImageObject',
                'url': base_url + '/web/image/website/1/logo',
            },
            'description': (
                'Freemoov est le spécialiste belge de la mobilité électrique : '
                'trottinettes électriques, gyroroues, vélos électriques, accessoires, '
                'réparation et conseil expert. Magasins à Liège et Namur.'
            ),
            'areaServed': [
                {'@type': 'Country', 'name': 'Belgium'},
                {'@type': 'Country', 'name': 'France'},
                {'@type': 'Country', 'name': 'Luxembourg'},
            ],
            'contactPoint': {
                '@type': 'ContactPoint',
                'contactType': 'customer service',
                'availableLanguage': 'French',
            },
            'sameAs': [
                'https://www.facebook.com/freemoov',
                'https://www.instagram.com/freemoov_be/',
            ],
            'hasMerchantReturnPolicy': ProductTemplateSeo._seo_return_policy(),
        }
        return Markup(json.dumps(data, ensure_ascii=False))

    # ------------------------------------------------------------------
    # LocalBusiness JSON-LD (store pages)
    # ------------------------------------------------------------------
    _STORE_HOURS = [
        {'@type': 'OpeningHoursSpecification', 'dayOfWeek': ['Tuesday', 'Wednesday', 'Thursday', 'Friday'], 'opens': '11:00', 'closes': '19:00'},
        {'@type': 'OpeningHoursSpecification', 'dayOfWeek': 'Saturday', 'opens': '11:00', 'closes': '17:00'},
    ]

    # Keep in sync with the published store pages. `path` is the live URL of
    # the page: Odoo appended a "-1" suffix to Liège and Namur when the pages
    # were recreated, and the previous hardcoded paths never matched, so no
    # store page ever carried its LocalBusiness markup.
    # `rating` is omitted where we have no verified Google Business figure —
    # never invent one, an unfounded aggregateRating is a policy violation.
    _STORES = {
        'liege': {
            'name': 'Freemoov Liège',
            'path': '/freemoov-liege-1',
            'street': 'Boulevard de la Sauvenière 136B',
            'locality': 'Liège',
            'postal_code': '4000',
            'latitude': 50.6413,
            'longitude': 5.5718,
            'rating': {'value': '4.9', 'count': 152},
        },
        'namur': {
            'name': 'Freemoov Namur',
            'path': '/freemoov-namur-1',
            'street': 'Avenue du Bourgmestre Jean Materne 120',
            'locality': 'Namur',
            'postal_code': '5100',
            'latitude': 50.4548,
            'longitude': 4.8365,
            'rating': {'value': '4.7', 'count': 196},
        },
        'charleroi': {
            'name': 'Freemoov Charleroi',
            'path': '/freemoov-charleroi',
            'street': 'Rue de Dampremy 69',
            'locality': 'Charleroi',
            'postal_code': '6000',
            'latitude': 50.4093,
            'longitude': 4.4399,
            'rating': None,
        },
    }

    # Which stores to describe on a given page. The store hub lists all three.
    _STORE_PAGES = {
        '/magasin': ('liege', 'namur', 'charleroi'),
        '/freemoov-liege-1': ('liege',),
        '/freemoov-liege': ('liege',),
        '/freemoov-namur-1': ('namur',),
        '/freemoov-namur': ('namur',),
        '/freemoov-charleroi': ('charleroi',),
    }

    _STORE_PHONE = '+32 81 65 91 66'

    def _get_store_jsonld(self, key):
        """Return the LocalBusiness JSON-LD of a single store."""
        store = self._STORES[key]
        base_url = self._seo_base_url()
        data = {
            '@context': 'https://schema.org',
            '@type': 'ElectronicsStore',
            '@id': '%s/#store-%s' % (base_url, key),
            'name': store['name'],
            'description': (
                'Magasin de trottinettes électriques, gyroroues et vélos '
                'électriques à %s. Conseil, vente et réparation.'
            ) % store['locality'],
            'image': base_url + '/web/image/website/1/logo',
            'url': base_url + store['path'],
            'telephone': self._STORE_PHONE,
            'address': {
                '@type': 'PostalAddress',
                'streetAddress': store['street'],
                'addressLocality': store['locality'],
                'postalCode': store['postal_code'],
                'addressCountry': 'BE',
            },
            'geo': {
                '@type': 'GeoCoordinates',
                'latitude': store['latitude'],
                'longitude': store['longitude'],
            },
            'openingHoursSpecification': self._STORE_HOURS,
            'priceRange': '€€',
            'parentOrganization': {'@type': 'Organization', '@id': base_url + '/#organization'},
        }
        if store['rating']:
            data['aggregateRating'] = {
                '@type': 'AggregateRating',
                'ratingValue': store['rating']['value'],
                'reviewCount': store['rating']['count'],
                'bestRating': 5,
            }
        return Markup(json.dumps(data, ensure_ascii=False))

    def get_store_jsonld_for_path(self, path):
        """Return the list of LocalBusiness JSON-LD blocks for a page path."""
        keys = self._STORE_PAGES.get((path or '').rstrip('/') or '/', ())
        return [self._get_store_jsonld(key) for key in keys]

    # ------------------------------------------------------------------
    # Noindex for navigation-only categories
    # ------------------------------------------------------------------
    def is_noindex_category_path(self, path):
        """True when `path` is a category page flagged `seo_noindex`."""
        match = re.match(r'^/shop/category/.*-(\d+)$', (path or '').rstrip('/'))
        if not match:
            return False
        category = self.env['product.public.category'].sudo().browse(int(match.group(1)))
        return bool(category.exists() and category.seo_noindex)

    def get_store_meta_description(self, path):
        """Fallback meta description for the store pages.

        The store pages were built in the website editor and none of them has
        a meta description, so Google composes its own snippet. This only acts
        as a default: anything typed in the SEO panel still wins (see the
        `meta_description` resolution order in website.layout).
        """
        keys = self._STORE_PAGES.get((path or '').rstrip('/') or '/', ())
        if not keys:
            return ''
        if len(keys) > 1:
            cities = ', '.join(self._STORES[k]['locality'] for k in keys)
            return (
                'Nos magasins de trottinettes électriques, vélos électriques et '
                'gyroroues à %s. Essai sur place, conseil expert, atelier de '
                'réparation et retrait de commande.'
            ) % cities
        store = self._STORES[keys[0]]
        return (
            'Magasin de trottinettes électriques, vélos électriques et gyroroues '
            'à %s — %s. Essai sur place, conseil expert et atelier de réparation. '
            'Ouvert du mardi au samedi.'
        ) % (store['locality'], store['street'])

    def get_jsonld_website(self):
        base_url = self._seo_base_url()
        data = {
            '@context': 'https://schema.org',
            '@type': 'WebSite',
            '@id': base_url + '/#website',
            'name': 'Freemoov',
            'url': base_url,
            'inLanguage': 'fr-BE',
            'publisher': {'@type': 'Organization', '@id': base_url + '/#organization'},
            'potentialAction': {
                '@type': 'SearchAction',
                'target': {
                    '@type': 'EntryPoint',
                    'urlTemplate': base_url + '/shop?search={search_term_string}',
                },
                'query-input': 'required name=search_term_string',
            },
        }
        return Markup(json.dumps(data, ensure_ascii=False))
