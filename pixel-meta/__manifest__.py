# Copyright © 2018 Garazd Creation (https://garazd.biz)
# @author: Yurii Razumovskyi (support@garazd.biz)
# @author: Iryna Razumovska (support@garazd.biz)
# License OPL-1 (https://www.odoo.com/documentation/15.0/legal/licenses.html).

# flake8: noqa: E501

{
    'name': 'Odoo Facebook Pixel Integration',
    'version': '16.0.3.1.0',
    'category': 'Website',
    'author': 'Garazd Creation',
    'website': 'https://garazd.biz/shop',
    'license': 'OPL-1',
    'summary': 'Add the Facebook Pixel event "PageView" to all website pages | Facebook Pixel Integration | Meta Pixel Integration | Website activity tracking',
    'images': ['static/description/banner.png', 'static/description/icon.png'],
    'live_test_url': 'https://garazd.biz/r/KFc',
    'depends': [
        'website_cookies_consent',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/website_templates.xml',
        'views/website_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pixel-meta/static/src/js/cookies_bar.js',
        ],
    },
    'price': 10.00,
    'currency': 'EUR',
    'support': 'support@garazd.biz',
    'application': True,
    'installable': True,
    'auto_install': False,
}
