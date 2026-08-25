from odoo import http
from odoo.http import request
from datetime import datetime
from odoo.addons.http_routing.models.ir_http import slug, unslug_url
from odoo import fields, http, SUPERUSER_ID, tools, _
from odoo.tools import lazy
from odoo.addons.website.controllers.main import Website
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteFreemoov(Website):

    @http.route()
    def get_dynamic_filter(self, filter_id, template_key, limit=None, search_domain=None, with_sample=False, productTemplateId=None):
        """Déclare productTemplateId, envoyé par le JS core des snippets
        produits dynamiques (s_dynamic_snippet_products) mais absent de la
        signature du contrôleur core, ce qui génère un WARNING "called
        ignoring args" à chaque appel. Le paramètre est consommé côté serveur
        via request.params dans les actions serveur de website_sale
        (data/data.xml), donc il suffit de le déclarer sans le transmettre.
        """
        return super().get_dynamic_filter(filter_id, template_key, limit, search_domain, with_sample)


class WebsiteCategoryController(http.Controller):

    @http.route('/fetch_subcategories', type='json', auth='public', website=True)
    def fetch_subcategories(self, category_id=None):
        sub_catg = ''
        if category_id:
            category = request.env['product.public.category'].browse(int(category_id))
            subcategories_ids = category.child_id
            sub_catg = request.env['ir.ui.view']._render_template(
                "website_freemoov.subcategory_template",
                {'subcategories_ids': subcategories_ids, 'category': category}
            )
            return {'sub_catg': sub_catg, 'category': slug(category)}
        return ""

    @http.route('/shop/cart/popover', type='json', auth='public', website=True)
    def cart_popover(self, **kwargs):
        order = request.website.sale_get_order()
        html = request.env['ir.ui.view']._render_template(
            "website_freemoov.cart_popover",
            {'website_sale_order': order}
        )
        return {'html': html}


class WebsiteSaleFreemoov(WebsiteSale):
    """Performance overrides for the catalog grid.

    Replaces the per-product N+1 stock lookup driven by
    `ProductTemplate.get_stock_availability(website)` (called in the QWeb
    `inherit_buttons` template) with a single `_read_group` for the whole
    grid, exposed via the `get_stock_availability(product)` qcontext callable.
    Wrapped in `lazy(...)` so that the batch query only fires if the template
    actually consumes the value.
    """

    def _get_additional_extra_shop_values(self, values, **post):
        res = super()._get_additional_extra_shop_values(values, **post)
        products = values.get('products')
        if products:
            website = request.website
            stock_data = lazy(lambda: self._freemoov_batch_stock_availability(products, website))
            res['get_stock_availability'] = lambda product: stock_data[product.id]
        return res

    def _freemoov_batch_stock_availability(self, products, website):
        """Build {template_id: {qty_avail, is_dropship, allow_out_of_stock}}
        for the whole grid in one stock.quant read_group.

        Mirrors the contract of ProductTemplate.get_stock_availability() so
        the template can keep using the same dict keys.
        """
        env = request.env
        dropship_route_id = env['website'].sudo()._freemoov_get_dropship_route_id()

        # sudo: public visitors have no ACL on stock.route; only booleans leave here
        products = products.sudo()

        # Single prefetch for fields touched in the loop below
        products.read(['detailed_type', 'allow_out_of_stock_order', 'route_ids', 'product_variant_ids'])

        stockable = products.filtered(
            lambda p: p.detailed_type == 'product' and not p.allow_out_of_stock_order
        )

        qty_per_variant = {}
        # sudo: les visiteurs publics n'ont pas d'ACL sur stock.warehouse ;
        # seul l'id de l'emplacement sert au domaine du _read_group sudoé.
        website_sudo = website.sudo() if website else website
        if stockable and website_sudo and website_sudo.warehouse_id:
            loc_id = website_sudo.warehouse_id.lot_stock_id.id
            variant_ids = stockable.product_variant_ids.ids
            if variant_ids:
                groups = env['stock.quant'].sudo()._read_group(
                    domain=[
                        ('product_id', 'in', variant_ids),
                        ('location_id', '=', loc_id),
                        ('on_hand', '=', True),
                    ],
                    groupby=['product_id'],
                    aggregates=['quantity:sum'],
                )
                qty_per_variant = {product.id: qty for product, qty in groups}

        result = {}
        for tmpl in products:
            if tmpl.detailed_type != 'product' or tmpl.allow_out_of_stock_order:
                qty_avail = 1
            else:
                qty_avail = sum(qty_per_variant.get(v.id, 0) for v in tmpl.product_variant_ids)
            is_dropship = bool(dropship_route_id and dropship_route_id in tmpl.route_ids.ids)
            result[tmpl.id] = {
                'qty_avail': qty_avail,
                'is_dropship': is_dropship,
                'allow_out_of_stock': tmpl.allow_out_of_stock_order,
            }
        return result
