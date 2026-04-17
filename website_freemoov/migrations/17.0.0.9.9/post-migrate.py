# -*- coding: utf-8 -*-
"""
Post-migration 17.0.0.9.9 — désactive la COW v16 `website_sale.wizard_checkout`
qui override totalement le template avec un rendu `.progress-wizard` v16 au
design cassé en v17 (texte stepper empilé verticalement en vert).

Notre inherit `website_freemoov.fm_wizard_checkout` prend désormais le relai
avec un design v17 propre (3 cercles numérotés Panier / Informations /
Confirmation). Il cible le `<t t-call="website.step_wizard">` du template
core v17 — donc la COW full-override doit être désactivée pour que le core
rende et que notre inherit s'applique.

Idempotent : si la COW n'existe pas ou est déjà inactive, no-op.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    cows = env['ir.ui.view'].with_context(active_test=False).search([
        ('key', '=', 'website_sale.wizard_checkout'),
        ('website_id', '!=', False),
        ('active', '=', True),
    ])
    if not cows:
        _logger.info(
            "[17.0.0.9.9] No active wizard_checkout COW — nothing to do."
        )
    else:
        cow_summary = [(c.id, c.website_id.id) for c in cows]
        cows.write({'active': False})
        _logger.info(
            "[17.0.0.9.9] Deactivated %d wizard_checkout COW(s): %s",
            len(cows), cow_summary,
        )

    env.registry.clear_cache()
    _logger.info("[17.0.0.9.9] Post-migrate complete — cache cleared")
