# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Website Freemoov',
    'category': 'Website',
    'version': '16.0.0.0.4',
    'summary': 'Website Freemoov',
    'author': '',
    'website' : '',
    'sequence': 1,
    'description': """Website Freemoov""",
    'depends': [
        'website',
        'web_editor',
        'website_sale',
        'website_sale_wishlist',
        'website_blog',
        'website_sale_comparison',
        'ust_common_features',
        'website_sale_stock_wishlist',
    ],
    'data':[
        'security/ir.model.access.csv',
        'views/header_freemoov_template.xml',
        'views/footer_template.xml',
        'views/modal_customize_template.xml',
        'views/product_attribute_views.xml',
        'views/homepage_template.xml',
        'views/inherited_product_template_view.xml',
        'views/inherited_template.xml',
    ],

    'assets': {
        'web.assets_frontend': [
            'website_freemoov/static/src/scss/feather.css',
            'website_freemoov/static/src/scss/common.scss',
            'website_freemoov/static/src/scss/header.scss',
            'website_freemoov/static/src/scss/footer.scss',
            'website_freemoov/static/src/scss/homepage.scss',
            'website_freemoov/static/src/scss/shop.scss',
            'website_freemoov/static/src/scss/product_detail.scss',
            'website_freemoov/static/src/js/common.js',
            'website_freemoov/static/src/js/variant.js',
            'website_freemoov/static/src/xml/stock_availability.xml',
        ],
        
        'web._assets_primary_variables': [
            'website_freemoov/static/src/scss/theme_variable.scss',
        ],
    },

    'images': [
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}

