from odoo import http
from odoo.http import request
from odoo.addons.http_routing.models.ir_http import slug, unslug_url

class WebsiteCategoryController(http.Controller):

    @http.route('/fetch_subcategories', type='json', auth='public', website=True)
    def fetch_subcategories(self, category_id=None):
        sub_catg =  ''
        if category_id:
            category = request.env['product.public.category'].browse(int(category_id))
            subcategories_ids = category.child_id
            sub_catg = request.env['ir.ui.view']._render_template("website_freemoov.subcategory_template",{'subcategories_ids':subcategories_ids,'category':category})
            return {'sub_catg':sub_catg,'category': slug(category)}
        return ""