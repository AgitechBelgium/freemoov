# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
# Developed by Upstackers Technologies
# Odoo 17 Migration: Simplified to use parent controller methods

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebUstSlider(http.Controller):

    # All in one product
    @http.route(['/slider_s/all_in_one_data'], type='http', auth='public', website=True)
    def ust_get_all_slider_data(self, **post):
        if post.get('style_id'):
            slider_ids = request.env['all_in.one.slider'].sudo().search(
                [('id', '=', int(post.get('style_id')))])
            values = {
                'ust_s_main': slider_ids,
            }
            return request.render("ust_common_features.ust_all_one_temp", values)

    @http.route(['/slider_s/get_all_slider_time_data'], type='json', auth='public', website=True)
    def get_all_slider_time_data(self, **post):
        slider_id = request.env['all_in.one.slider'].search([('id', '=', int(post.get('all_slider_id')))])
        slider_data = {
            'slider_id': 'ust-'  + str(slider_id.id),
            'no_counts': slider_id.item_each_slide,
            'slider_auto_slide': slider_id.slider_auto_slide,
            'slider_auto_play_time': slider_id.speed_of_slider,
        }
        return slider_data


class CustomWebsiteSale(WebsiteSale):
    """
    Odoo 17 Migration: This controller now extends the parent shop() method
    instead of overriding it completely. This ensures compatibility with
    Odoo 17's changed method signatures.
    
    Customization: Forces layout_mode based on category presence.
    """

    @http.route()
    def shop(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, ppg=False, **post):
        # Call parent shop method (Odoo 17 compatible)
        response = super().shop(
            page=page,
            category=category,
            search=search,
            min_price=min_price,
            max_price=max_price,
            ppg=ppg,
            **post
        )
        
        # Apply custom layout_mode logic
        if hasattr(response, 'qcontext'):
            if category:
                response.qcontext['layout_mode'] = 'list'
            else:
                response.qcontext['layout_mode'] = 'grid'
        
        return response
