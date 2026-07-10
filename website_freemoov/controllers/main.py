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
