# -*- coding: utf-8 -*-
{
    'name': 'Payment Provider: FLOA Pay',
    'version': '17.0.1.0.1',
    'category': 'Accounting/Payment Providers',
    'summary': 'FLOA BNPL — Paiement en 3x pour la Belgique',
    'author': 'Freemoov',
    'website': 'https://freemoov.be',
    'depends': [
        'payment',
        'website_sale',
        'website_freemoov',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_floa_templates.xml',
        'views/payment_provider_views.xml',
        'views/res_partner_views.xml',
        'views/floa_widget_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'demo': [
        'data/payment_provider_sandbox_demo.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_floa/static/src/scss/floa_widget.scss',
            'payment_floa/static/src/js/floa_widget.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
