# -*- coding: utf-8 -*-
"""
Post-migration 17.0.0.9.6 — rollback de la 9.5.

La 17.0.0.9.5 désactivait 7 COW payment/delivery/confirmation pour résoudre
un crash JS v17 (_isPickupLocationSelected → null.parentElement). Solution
trop brutale : cette désactivation a aussi supprimé tout le design custom
CMS v16 (labels, sections personnalisées, layout sidebar).

Décision produit : préserver le design CMS v16 tel quel pour ne pas dégrader
l'apparence du site. Le crash JS sur /shop/payment est un coût acceptable
tant qu'une refonte checkout propre (option C : port en code source) n'a
pas été livrée dans une itération dédiée.

Ce script réactive les 7 COW désactivées par la 9.5. Idempotent — si une
COW n'existe pas ou est déjà active, aucun changement.
"""
import logging

_logger = logging.getLogger(__name__)


PAYMENT_COW_KEYS = (
    'website_sale.payment',
    'website_sale.payment_delivery',
    'website_sale_delivery.payment_delivery_methods',
    'website_sale_picking.checkout_delivery',
    'website_sale_picking.payment_confirmation_status',
    'website_sale.payment_confirmation_status',
    'website_sale.payment_oe_structure_website_sale_payment_1',
    'website_sale.payment_oe_structure_website_sale_payment_2',
)


def _reactivate_payment_cows(env):
    cows = env['ir.ui.view'].with_context(active_test=False).search([
        ('key', 'in', PAYMENT_COW_KEYS),
        ('website_id', '!=', False),
        ('active', '=', False),
    ])
    if not cows:
        _logger.info("[17.0.0.9.6] No inactive payment COW to reactivate.")
        return

    cow_summary = [(c.id, c.key, c.website_id.id) for c in cows]
    cows.write({'active': True})
    _logger.info(
        "[17.0.0.9.6] Re-activated %d payment COW(s) (rollback of 17.0.0.9.5): %s",
        len(cows), cow_summary,
    )


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    _reactivate_payment_cows(env)
    env.registry.clear_cache()
    _logger.info("[17.0.0.9.6] Post-migrate complete — cache cleared")
