# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

from . import models
from . import controllers

# Pages CMS créées via le website builder en production et liées en dur par
# les templates du module (footer, fiches produit, ...). Sur une base fraîche
# (builds de dev Odoo.sh), elles n'existent pas et le crawler des tests
# standards (website Crawler.test_10/test_20) échoue en 404.
_LINKED_CMS_PAGES = {
    '/payez-par-mois': 'Payez par mois',
    '/magasin': 'Magasin',
    '/about': 'Qui sommes-nous ?',
    '/services-atelier': 'Services atelier',
    '/garantie': 'Garantie',
    '/delivery': 'Livraison',
    '/return': 'Retour',
    '/cookie-policy': 'Cookies',
    '/privacy-policy': 'Données personnelles',
    '/terms': 'Conditions générales',
}

# Le test core website TestPage.test_copy_page clone une page nommée
# "about-us" et exige qu'aucune website.page préexistante ne porte cette URL
# exacte : pour /about-us on pose donc une redirection au lieu d'une page —
# le crawler des tests standards suit les redirections internes.
_LINKED_CMS_REDIRECTS = {
    '/about-us': '/about',
}


def _ensure_linked_cms_pages(env):
    """Crée une page placeholder publiée pour chaque URL liée en dur qui n'a
    pas encore de website.page. Ne tourne qu'à l'installation du module : sur
    les bases existantes (prod/staging) les vraies pages sont déjà en base et
    rien n'est créé ni modifié."""
    Rewrite = env['website.rewrite']
    for url_from, url_to in _LINKED_CMS_REDIRECTS.items():
        if Rewrite.sudo().search_count([('url_from', '=', url_from)]):
            continue
        Rewrite.sudo().create({
            'name': 'CI placeholder %s' % url_from,
            'url_from': url_from,
            'url_to': url_to,
            'redirect_type': '302',
        })

    Page = env['website.page']
    for url, name in _LINKED_CMS_PAGES.items():
        if Page.sudo().search_count([('url', '=', url)]):
            continue
        key = 'website_freemoov.cms%s' % url.replace('-', '_').replace('/', '_')
        Page.sudo().create({
            'name': name,
            'type': 'qweb',
            'url': url,
            'is_published': True,
            'website_id': False,
            'key': key,
            'arch': (
                '<t t-name="%(key)s">'
                '<t t-call="website.layout">'
                '<div id="wrap" class="oe_structure">'
                '<section class="s_text_block pt40 pb40">'
                '<div class="container"><h1>%(title)s</h1></div>'
                '</section>'
                '</div>'
                '</t>'
                '</t>'
            ) % {'key': key, 'title': name},
        })