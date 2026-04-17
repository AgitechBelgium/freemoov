# -*- coding: utf-8 -*-
"""
Post-migration 17.0.0.9.4 — fixe les xpath v16 obsolètes dans les COW cart.

En v16, `website_sale.cart_lines` utilisait `<table id="cart_products">` pour
l'affichage du panier. En v17, c'est devenu un `<div id="cart_products">` avec
une structure flex/card.

Les vues COW (website-specific) qui inherit_id `website_sale.cart_lines` avec
un xpath `//table[@id='cart_products']` ne peuvent plus être localisées et
font crasher toute la page panier (ValueError: xpath ne peut être localisé).

Symptôme observé : 500 Internal Server Error sur /shop/cart après upgrade.

Fix : remplacer `//table[@id='cart_products']` par `//div[@id='cart_products']`
dans les arches concernés (opération idempotente, safe si déjà fixed).

COWs typiquement affectés :
- website_sale.suggested_products_list (accessoires recommandés CMS)
- potentiellement d'autres COWs custom ajoutés via le builder website
"""
import logging

_logger = logging.getLogger(__name__)


LEGACY_XPATH_CART = "//table[@id='cart_products']"
V17_XPATH_CART = "//div[@id='cart_products']"


def _fix_cart_products_xpath(env):
    cows = env['ir.ui.view'].with_context(active_test=False).search([
        ('website_id', '!=', False),
        ('arch_db', 'ilike', LEGACY_XPATH_CART.replace("'", "%")),
    ])
    fixed_ids = []
    for cow in cows:
        arch = cow.arch_db or ''
        if LEGACY_XPATH_CART in arch:
            cow.arch_db = arch.replace(LEGACY_XPATH_CART, V17_XPATH_CART)
            fixed_ids.append((cow.id, cow.key))

    if fixed_ids:
        _logger.info(
            "[17.0.0.9.4] Fixed %d COW(s) with legacy cart xpath: %s",
            len(fixed_ids), fixed_ids,
        )
    else:
        _logger.info("[17.0.0.9.4] No legacy cart xpath found in COWs.")


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    _fix_cart_products_xpath(env)
    env.registry.clear_cache()
    _logger.info("[17.0.0.9.4] Post-migrate complete — cache cleared")
