# -*- coding: utf-8 -*-
"""
Post-migration 17.0.0.9.8 — injecte les éléments DOM v17 manquants dans le
COW `website_sale_delivery.payment_delivery_methods` pour débloquer le crash
JS `_isPickupLocationSelected → null.parentElement` au click carrier sur
/shop/payment.

Le COW v16 (website-specific) override totalement le template core sans
rendre `.o_order_location`, `.o_show_pickup_locations`,
`.o_list_pickup_locations` — éléments que le JS v17 `website_sale_delivery`
fait `querySelector()` sans null-check.

On injecte ces éléments juste avant le `<t t-if="delivery.website_description">`
final, dans un wrapper `.d-none` pour ne pas altérer le visuel.
Opération idempotente : vérifie la présence de `.o_order_location` avant
modification.
"""
import logging

_logger = logging.getLogger(__name__)


TARGET_KEY = 'website_sale.payment_delivery_methods'

# Bloc v17-compliant à insérer pour fournir les hooks DOM attendus par le
# JS `website_sale_delivery._isPickupLocationSelected` / `_onClickShowLocations`.
DOM_HOOKS_BLOCK = """
        <t t-set="delivery_method" t-value="delivery.delivery_type+'_use_locations'"/>
        <div class="small">
            <div class="d-none">
                <span class="o_order_location">
                    <b class="o_order_location_name"/>
                    <br/>
                    <i class="o_order_location_address"/>
                </span>
                <span class="fa fa-times ms-2 o_remove_order_location" aria-label="Remove this location" title="Remove this location"/>
            </div>
            <t t-if="delivery_method in delivery.fields_get() and delivery[delivery_method]">
                <div class="o_show_pickup_locations"/>
                <div class="o_list_pickup_locations"/>
            </t>
        </div>
"""

# Marqueur unique qu'on va chercher pour insérer AVANT.
# Le `<t t-if="delivery.website_description">` est la fin de structure commune
# à v16 et v17 du template.
ANCHOR = '<t t-if="delivery.website_description">'


def _patch_cow_arch(env):
    cows = env['ir.ui.view'].with_context(active_test=False).search([
        ('key', '=', TARGET_KEY),
        ('website_id', '!=', False),
        ('active', '=', True),
    ])
    if not cows:
        _logger.info(
            "[17.0.0.9.8] No active COW %r — nothing to patch.", TARGET_KEY,
        )
        return

    patched = []
    for cow in cows:
        arch = cow.arch_db or ''
        if 'o_order_location' in arch:
            _logger.info(
                "[17.0.0.9.8] COW id=%d already has o_order_location, skip.",
                cow.id,
            )
            continue
        if ANCHOR not in arch:
            _logger.warning(
                "[17.0.0.9.8] COW id=%d key=%r: anchor %r not found, "
                "cannot inject DOM hooks safely. Skipping.",
                cow.id, cow.key, ANCHOR,
            )
            continue

        new_arch = arch.replace(ANCHOR, DOM_HOOKS_BLOCK + '        ' + ANCHOR, 1)
        cow.arch_db = new_arch
        patched.append((cow.id, cow.website_id.id))

    if patched:
        _logger.info(
            "[17.0.0.9.8] Injected v17 DOM hooks into %d COW(s): %s",
            len(patched), patched,
        )
    else:
        _logger.info("[17.0.0.9.8] No COW required patching.")


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    _patch_cow_arch(env)
    env.registry.clear_cache()
    _logger.info("[17.0.0.9.8] Post-migrate complete — cache cleared")
