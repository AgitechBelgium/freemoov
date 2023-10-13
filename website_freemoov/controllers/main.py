from odoo import http
from odoo.http import request

class WebsiteCategoryController(http.Controller):

    @http.route('/fetch_subcategories', type='json', auth='public', website=True)
    def fetch_subcategories(self, category_id=None):
        sub_catg =  ''
        if category_id:
            category = request.env['product.public.category'].browse(int(category_id))
            subcategories_ids = category.child_id
            sub_catg = request.env['ir.ui.view']._render_template("website_freemoov.subcategory_template",{'subcategories_ids':subcategories_ids})
            return {'sub_catg':sub_catg}
        return ""