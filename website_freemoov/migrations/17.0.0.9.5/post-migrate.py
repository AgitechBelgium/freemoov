# -*- coding: utf-8 -*-
"""
Post-migration 17.0.0.9.5 — purge COW full-override du checkout v16.

Certaines vues `website_sale.payment`, `website_sale.payment_delivery`,
`website_sale_delivery.payment_delivery_methods` et
`website_sale_picking.checkout_delivery` existent en DB comme COW
(website_id != NULL) qui surchargent ENTIÈREMENT le template core
(via `<t t-name="..."/>` au lieu de `<data inherit_id="..."/>`).

Ces COW ont été créées via le builder CMS en v16 et contiennent :
- structure DOM v16 sans les éléments `.o_order_location`,
  `.o_show_pickup_locations`, `.o_list_pickup_locations` que le JS
  `website_sale_delivery` v17 attend
- xpath vers des éléments qui n'existent plus en v17

Symptômes :
- 500 sur `/shop/payment` ou JS error au click carrier :
  `TypeError: Cannot read properties of null (reading 'parentElement')`
  `at _isPickupLocationSelected`

Fix : désactiver ces COW. Le core v17 reprend la main sur le rendu et
notre module `website_freemoov.checkout_templates` applique ses
inherits propres (labels FR, boutons, stepper, reassurance).

Les customisations visuelles CMS v16 sur le payment page sont perdues
— acceptable car notre refonte checkout couvre le rendu.
"""
import logging

_logger = logging.getLogger(__name__)


# COW à désactiver (override total de templates core devenus incompatibles v17).
# On désactive au lieu de supprimer pour garder une trace et permettre rollback
# via l'admin web interface si besoin.
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


def _deactivate_payment_cows(env):
    cows = env['ir.ui.view'].with_context(active_test=False).search([
        ('key', 'in', PAYMENT_COW_KEYS),
        ('website_id', '!=', False),
        ('active', '=', True),
    ])
    if not cows:
        _logger.info("[17.0.0.9.5] No active payment COW to deactivate.")
        return

    cow_summary = [(c.id, c.key, c.website_id.id) for c in cows]
    cows.write({'active': False})
    _logger.info(
        "[17.0.0.9.5] Deactivated %d payment COW(s): %s",
        len(cows), cow_summary,
    )


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    _deactivate_payment_cows(env)
    env.registry.clear_cache()
    _logger.info("[17.0.0.9.5] Post-migrate complete — cache cleared")
