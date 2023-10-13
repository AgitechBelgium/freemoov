# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
# Developed by Upstackers Technologies

{
    'name': 'Upstackers E-commerce Common Features',
    'category': 'Website',
    'version': '16.0.0.0.0',
    'summary': 'Upstackers E-commerce Common Features',
    'author': 'Upstackers Technologies',
    'website' : 'https://www.upstackers.com',
    'sequence': 1,
    'description': """Base module containing common libraries for Theme Fashico""",
    'depends': [
        'website',
        'website_blog',
        'web_editor',
        'website_sale',
        'website_sale_wishlist',
        'sale_management',
        'website_sale_comparison',
        'product',
        'portal',
    ],
    'data':[
        'security/ir.model.access.csv',
        'views/ust_slider_snippets_view.xml',
        'views/template.xml',
        'views/product_template_view.xml',
        'views/snippets/ust_dynamic_snippets.xml',
        'views/snippets/ust_all_in_one_slider.xml',
        'views/menu_item.xml',
    ],

    'assets': {
        'web.assets_frontend': [
            'ust_common_features/static/ust-lib/css/owl.carousel.min.css',
            'ust_common_features/static/src/scss/all_in_one_slider.scss',
            'ust_common_features/static/src/scss/common.scss',


            'ust_common_features/static/ust-lib/js/owl.carousel.js',
            'ust_common_features/static/src/js/snippets/ust_all_in_one_frontend.js',
            'ust_common_features/static/src/js/ust_carousel_product.js',
        ],

        'web_editor.assets_wysiwyg': [
            'ust_common_features/static/src/js/snippets/ust_all_in_one_s.js',
            'ust_common_features/static/src/xml/ust_snippet_templete/ust_slider_snippet.xml',
        ],
    },
    
    'images': [
        'static/description/banner.jpg',
    ],

    'license': 'OPL-1',
    'price': 30,
    'currency': 'EUR',
    'installable': True,
    'application': True,
    'auto_install': False,
}
