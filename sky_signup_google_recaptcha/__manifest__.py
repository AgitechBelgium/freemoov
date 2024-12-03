# -*- encoding: utf-8 -*-
#########################################################################################
#
#    Copyright (C) 2019 Skyscend Business Solutions (https://www.skyscendbs.com)
#    Copyright (C) 2020 Skyscend Business Solutions  Pvt. Ltd.(<https://skyscendbs.com>)
#
#########################################################################################

{
    'name': 'Sky SingUp Google reCAPTCHA integration',
    'version': '16.0.1.1.0',
    'license': 'AGPL-3',
    'description': """
     Adds Google reCAPTCHA validation to Odoo signup form for enhanced security.       
    """,
    'author': 'Skyscend Business Solutions Pvt. Ltd.',
    'website': 'https://www.skyscendbs.com',
    'depends': [
        'google_recaptcha'
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/auth_signup_login_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'sky_signup_google_recaptcha/static/src/js/signup.js',
        ],
    },
    'installable': True,
}
