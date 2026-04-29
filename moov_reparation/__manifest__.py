# -*- coding: utf-8 -*-

{
    'name': 'Reparation Sequence',
    'version': '17.0.1.0.2',
    'depends': [
        'project',
        'industry_fsm',
        'pos_sale',
    ],
    'data': [
        'data/sequence.xml',
        'views/task.xml',
        'views/sms_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'moov_reparation/static/src/scss/pos_category_selector.scss',
            'moov_reparation/static/src/js/pos_settle_qty.js',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'demo': [
    ],
}
