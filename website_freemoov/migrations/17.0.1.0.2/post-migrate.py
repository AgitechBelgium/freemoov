# -*- coding: utf-8 -*-
"""Post-migration 17.0.1.0.2 — fix v16 broken COWs identified after go-live.

Catégorie de bugs traités :
- COW (website-specific) du template `website_sale.cart_lines` qui appelle
  `product._get_combination_info_variant(pricelist=...)`. En v17 la signature
  de `_get_combination_info` n'accepte plus le kwarg `pricelist` (passe par
  le context). La COW plantait le cart avec :
    TypeError: ProductTemplate._get_combination_info() got an unexpected
    keyword argument 'pricelist'

Au go-live prod 2026-04-19 on a disable la COW en SQL pour débloquer le
cart. Ce script la ré-active avec la syntaxe v17 corrigée.

Idempotent : ré-exécution sans effet si la COW est déjà en syntaxe v17.
"""
import logging

_logger = logging.getLogger(__name__)


# Patches à appliquer sur les arch_db multilingues (jsonb Odoo).
# Clé = pattern v16 à remplacer, valeur = équivalent v17.
ARCH_PATCHES = [
    (
        'product._get_combination_info_variant(pricelist=website_sale_order.pricelist_id)',
        "product.with_context(pricelist=website_sale_order.pricelist_id.id)._get_combination_info_variant()",
    ),
]


def _patch_view_arch(cr, view_id):
    """Applique les remplacements v16→v17 sur un arch_db jsonb multilingue."""
    cr.execute(
        "SELECT arch_db FROM ir_ui_view WHERE id = %s",
        (view_id,),
    )
    row = cr.fetchone()
    if not row or not row[0]:
        return False
    arch = row[0]
    modified = False
    for lang, value in list(arch.items()):
        new_value = value
        for v16, v17 in ARCH_PATCHES:
            if v16 in new_value:
                new_value = new_value.replace(v16, v17)
                modified = True
        arch[lang] = new_value
    if modified:
        cr.execute(
            "UPDATE ir_ui_view SET arch_db = %s, active = true WHERE id = %s",
            (__import__('json').dumps(arch), view_id),
        )
    return modified


def _fix_cart_lines_suggested_products_cow(env):
    """Fix la COW website_sale.suggested_products_list (cart accessory products)."""
    cr = env.cr
    cr.execute("""
        SELECT id FROM ir_ui_view
        WHERE key = 'website_sale.suggested_products_list'
          AND website_id IS NOT NULL
          AND arch_db::text LIKE '%%pricelist=website_sale_order.pricelist_id)%%'
    """)
    rows = cr.fetchall()
    if not rows:
        _logger.info("[17.0.1.0.2] No broken cart suggested_products_list COW found")
        return
    for (view_id,) in rows:
        if _patch_view_arch(cr, view_id):
            _logger.info(
                "[17.0.1.0.2] Patched + reactivated COW id=%d "
                "(website_sale.suggested_products_list) with v17 syntax",
                view_id,
            )
        else:
            _logger.info(
                "[17.0.1.0.2] COW id=%d already v17-compatible, skipped",
                view_id,
            )


def _normalize_boolean_params(cr):
    """Odoo's res.config.settings stores Boolean config_parameter as repr(bool)
    i.e. the strings "True" / "False". default_get then calls bool(value) to
    populate the field, and bool("False") is True because "False" is a
    non-empty string. Users see the checkbox re-ticking itself on every
    settings load. Normalize "False" to "" so bool("") is False.
    """
    cr.execute("""
        UPDATE ir_config_parameter SET value = ''
        WHERE key IN ('website_freemoov.maintenance_mode_active',
                      'website_freemoov.maintenance_banner_active')
          AND value = 'False'
        RETURNING key
    """)
    for row in cr.fetchall():
        _logger.info("[17.0.1.0.2] Normalized boolean param %s: 'False' -> ''", row[0])


def _restore_broken_view_keys(cr):
    """The upgrade platform's end-01-attrs-views script stripped the 'key'
    field of several custom views that failed its v16→v17 attrs migration,
    leaving them findable neither by module update nor by env.ref. Rebuild
    the key from ir_model_data for every view whose xml_id is known and
    whose key is blank.
    """
    cr.execute("""
        UPDATE ir_ui_view v
           SET key = d.module || '.' || d.name
          FROM ir_model_data d
         WHERE v.id = d.res_id
           AND d.model = 'ir.ui.view'
           AND d.module IN ('website_freemoov', 'google_merchant_center',
                            'moov_reparation', 'mask_as_done_extends',
                            'ust_common_features', 'website_cookies_consent',
                            'website_google_tag', 'sky_signup_google_recaptcha',
                            'pixel_meta')
           AND (v.key IS NULL OR v.key = '')
        RETURNING d.module, d.name
    """)
    count = cr.rowcount
    if count:
        _logger.info("[17.0.1.0.2] Restored 'key' on %d custom views", count)


def _disable_v16_payment_cows(cr):
    """Désactive les COWs v16 du /shop/payment qui testent les anciennes
    variables `providers`/`tokens` au lieu de `payment_methods_sudo`/`tokens_sudo`.

    Symptôme en prod après migration : bandeau "Aucune option de paiement
    appropriée n'a pu être trouvée" alors que les providers sont actifs.
    En v17 les variables du controller sont `payment_methods_sudo` et
    `tokens_sudo` ; les COWs v16 continuent de chercher `providers` et
    `tokens` (vides) → le t-else du template affiche l'erreur.
    """
    cr.execute("""
        UPDATE ir_ui_view
           SET active = false
         WHERE website_id IS NOT NULL
           AND active = true
           AND (
                (key = 'website_sale.payment' AND arch_db::text LIKE '%%providers or tokens%%')
             OR (key = 'website_sale.payment_delivery'
                 AND inherit_id IN (SELECT id FROM ir_ui_view
                                    WHERE key = 'website_sale.payment' AND website_id IS NOT NULL))
           )
        RETURNING id, key
    """)
    for row in cr.fetchall():
        _logger.info("[17.0.1.0.2] Disabled v16 payment COW id=%d key=%s", row[0], row[1])


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    _fix_cart_lines_suggested_products_cow(env)
    _disable_v16_payment_cows(cr)
    _restore_broken_view_keys(cr)
    _normalize_boolean_params(cr)

    env.registry.clear_cache()
    _logger.info("[17.0.1.0.2] Post-migrate complete — cache cleared")
