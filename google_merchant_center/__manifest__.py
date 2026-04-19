# -*- coding: utf-8 -*-
{
    'name': 'Google Merchant Center',
    'category': 'Website',
    'version': '18.0.2.1',
    'summary': 'Sync produits vers Google Merchant Center via Merchant API',
    'description': """
        Synchronisation des produits Odoo vers Google Merchant Center.
        Titres et descriptions optimisés par type de produit,
        catégories Google automatiques, frais de port par pays,
        mode dry-run, cron 15 min, logs détaillés.
    """,
    'author': u'Enzo Naut\xe9',
    'website': 'https://freemoov.com',
    'depends': [
        'website_sale',
        'website_sale_stock',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/product_template_views.xml',
        'views/product_public_category_views.xml',
        'views/google_merchant_log_views.xml',
        'views/menu_views.xml',
        'wizards/google_merchant_sync_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
