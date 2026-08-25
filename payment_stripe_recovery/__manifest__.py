# -*- coding: utf-8 -*-
{
    'name': 'Stripe Payment Recovery',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'Réconciliation des paiements Stripe capturés mais non confirmés + anti double paiement',
    'author': 'Freemoov',
    'website': 'https://freemoov.be',
    'depends': [
        'payment_stripe',
        'sale',
    ],
    'data': [
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
