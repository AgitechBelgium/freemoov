# -*- coding: utf-8 -*-
"""Purge le microdata schema.org et les URLs legacy /shop/product/ du HTML
de sliders figé dans l'arch des pages éditées via le website builder.

Le template ust_all_in_one_slider n'émet plus de microdata (entités Product
incomplètes signalées par Search Console : champ image manquant), mais les
pages sauvegardées dans l'éditeur ont conservé une copie rendue de l'ancien
markup dans leur arch COW. Les vues de base des modules (website_id NULL,
hors website.page) ne sont pas touchées.
"""
import json
import re

_SPAN_MICRODATA = re.compile(
    r'\s*<span itemprop="(?:price|priceCurrency)" style="display:none;"[^>]*>[^<]*</span>')
_ITEMSCOPE = re.compile(r'\s*itemscope(?:="itemscope")?')
_ITEMTYPE = re.compile(r'\s*itemtype="https?://schema\.org/(?:Product|Offer)"')
_ITEMPROP = re.compile(r'\s*itemprop="(?:url|name|offers|price|priceCurrency|listPrice)"')


def _clean(arch):
    arch = _SPAN_MICRODATA.sub('', arch)
    arch = _ITEMSCOPE.sub('', arch)
    arch = _ITEMTYPE.sub('', arch)
    arch = _ITEMPROP.sub('', arch)
    return arch.replace('/shop/product/', '/shop/')


def migrate(cr, version):
    cr.execute(
        """
        SELECT v.id, v.arch_db
          FROM ir_ui_view v
         WHERE v.type = 'qweb'
           AND v.arch_db::text LIKE '%%ust-product-%%'
           AND (v.website_id IS NOT NULL
                OR v.id IN (SELECT view_id FROM website_page))
        """
    )
    for view_id, arch_db in cr.fetchall():
        if isinstance(arch_db, str):
            arch_db = json.loads(arch_db)
        cleaned = {lang: _clean(arch) for lang, arch in arch_db.items()}
        if cleaned != arch_db:
            cr.execute(
                "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                [json.dumps(cleaned), view_id],
            )
