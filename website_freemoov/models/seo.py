# -*- coding: utf-8 -*-
import json
import logging
import re
from datetime import timedelta

from markupsafe import Markup

from odoo import fields, models, api
from odoo.http import request
from odoo.tools import html2plaintext
from odoo.tools.translate import html_translate

_logger = logging.getLogger(__name__)

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
                    from odoo.addons.http_routing.models.ir_http import slug
                    url = '/shop/category/%s' % slug(categ) if categ else '/shop'
                    return request.redirect(url, code=301)
        return super()._serve_fallback()


class SeoMetadataFix(models.AbstractModel):
    """Fix og:image domain pointing to freemoov.odoo.com instead of the
    public website domain (www.freemoov.com)."""
    _inherit = 'website.seo.metadata'

    def get_website_meta(self):
        meta = super().get_website_meta()
        if not request:
            return meta
        website = request.website
        domain = website.domain or ''
        domain = domain.strip().rstrip('/')
        if not domain:
            domain = website.get_base_url().rstrip('/')
        if not domain or '.odoo.com' in domain:
            return meta
        if not domain.startswith('http'):
            domain = 'https://' + domain

        from urllib.parse import urlparse
        for bucket in ('default_opengraph', 'default_twitter', 'opengraph_meta', 'twitter_meta'):
            data = meta.get(bucket, {})
            for key in list(data.keys()):
                val = data[key]
                if isinstance(val, str) and '.odoo.com' in val:
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
        base_url = website.get_base_url()
        images = [base_url + website.image_url(self, 'image_1920')]
        for img in self.product_template_image_ids:
            images.append('%s/web/image/product.image/%s/image_1920' % (base_url, img.id))
        return images

    def _seo_description(self):
        """Return best available text description (summary > description_sale > name)."""
        if self.summary:
            text = html2plaintext(self.summary)
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
        base_url = self.env['website'].get_current_website().get_base_url()
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
        base_url = self.env['website'].get_current_website().get_base_url()
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
        base_url = self.env['website'].get_current_website().get_base_url()
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
        base_url = self.env['website'].get_current_website().get_base_url()
        items = [
            {'@type': 'ListItem', 'position': 1, 'name': 'Accueil', 'item': base_url + '/'},
        ]
        if category:
            items.append({
                '@type': 'ListItem', 'position': 2,
                'name': category.name,
                'item': base_url + '/shop/category/%s-%s' % (category.seo_name or category.name, category.id),
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
        base_url = self.env['website'].get_current_website().get_base_url()
        items = [
            {'@type': 'ListItem', 'position': 1, 'name': 'Accueil', 'item': base_url + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Produits', 'item': base_url + '/shop'},
        ]
        pos = 3
        for parent in reversed(self.parents_and_self[:-1]):
            items.append({
                '@type': 'ListItem', 'position': pos,
                'name': parent.name,
                'item': base_url + '/shop/category/%s-%s' % (parent.seo_name or parent.name, parent.id),
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
        base_url = self.env['website'].get_current_website().get_base_url()
        list_items = []
        for idx, product in enumerate(products[:36], start=1):
            list_items.append({
                '@type': 'ListItem',
                'position': idx,
                'item': {
                    '@type': 'Product',
                    'name': product.name,
                    'url': base_url + product.website_url,
                    'image': base_url + self.env['website'].get_current_website().image_url(product, 'image_512'),
                    'offers': {
                        '@type': 'Offer',
                        'price': '%.2f' % product.list_price,
                        'priceCurrency': 'EUR',
                    },
                },
            })
        data = {
            '@context': 'https://schema.org',
            '@type': 'CollectionPage',
            'name': self.name,
            'url': base_url + '/shop/category/%s-%s' % (self.seo_name or self.name, self.id),
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
    )

    def _enumerate_pages(self, query_string=None, force=False):
        for page in super()._enumerate_pages(query_string=query_string, force=force):
            loc = page.get('loc', '')
            if any(excl in loc for excl in self._SITEMAP_EXCLUDE):
                continue
            yield page

    # ------------------------------------------------------------------
    # Canonical: fix / vs /home
    # ------------------------------------------------------------------
    def _get_canonical_url(self, canonical_params=None):
        canonical = super()._get_canonical_url(canonical_params=canonical_params)
        base_url = self.get_base_url()
        if canonical.rstrip('/') == base_url + '/home':
            return base_url + '/'
        return canonical

    # ------------------------------------------------------------------
    # Organization JSON-LD (homepage only)
    # ------------------------------------------------------------------
    def get_jsonld_organization(self):
        base_url = self.get_base_url()
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

    def get_jsonld_local_business_liege(self):
        base_url = self.get_base_url()
        data = {
            '@context': 'https://schema.org',
            '@type': 'ElectronicsStore',
            '@id': base_url + '/#store-liege',
            'name': 'Freemoov Liège',
            'description': 'Magasin de trottinettes électriques, gyroroues et vélos électriques à Liège. Conseil, vente et réparation.',
            'image': base_url + '/web/image/website/1/logo',
            'url': base_url + '/freemoov-liege',
            'telephone': '+32 81 65 91 66',
            'address': {
                '@type': 'PostalAddress',
                'streetAddress': 'Boulevard de la Sauvenière 136B',
                'addressLocality': 'Liège',
                'postalCode': '4000',
                'addressCountry': 'BE',
            },
            'geo': {'@type': 'GeoCoordinates', 'latitude': 50.6413, 'longitude': 5.5718},
            'openingHoursSpecification': self._STORE_HOURS,
            'aggregateRating': {
                '@type': 'AggregateRating',
                'ratingValue': '4.9',
                'reviewCount': 152,
                'bestRating': 5,
            },
            'priceRange': '€€',
            'parentOrganization': {'@type': 'Organization', '@id': base_url + '/#organization'},
        }
        return Markup(json.dumps(data, ensure_ascii=False))

    def get_jsonld_local_business_namur(self):
        base_url = self.get_base_url()
        data = {
            '@context': 'https://schema.org',
            '@type': 'ElectronicsStore',
            '@id': base_url + '/#store-namur',
            'name': 'Freemoov Namur',
            'description': 'Magasin de trottinettes électriques, gyroroues et vélos électriques à Namur. Conseil, vente et réparation.',
            'image': base_url + '/web/image/website/1/logo',
            'url': base_url + '/freemoov-namur',
            'telephone': '+32 81 65 91 66',
            'address': {
                '@type': 'PostalAddress',
                'streetAddress': 'Avenue du Bourgmestre Jean Materne 120',
                'addressLocality': 'Namur',
                'postalCode': '5100',
                'addressCountry': 'BE',
            },
            'geo': {'@type': 'GeoCoordinates', 'latitude': 50.4548, 'longitude': 4.8365},
            'openingHoursSpecification': self._STORE_HOURS,
            'aggregateRating': {
                '@type': 'AggregateRating',
                'ratingValue': '4.7',
                'reviewCount': 196,
                'bestRating': 5,
            },
            'priceRange': '€€',
            'parentOrganization': {'@type': 'Organization', '@id': base_url + '/#organization'},
        }
        return Markup(json.dumps(data, ensure_ascii=False))

    def get_jsonld_website(self):
        base_url = self.get_base_url()
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
