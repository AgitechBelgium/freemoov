# -*- coding: utf-8 -*-
"""
Pre-migration 17.0.0.9.9 — désactive toutes les COW v16 qui override
totalement les templates core du checkout (cart, wizard, address, payment).

Option C validée par l'utilisateur : le design checkout est porté en code
source via des inherits v17 propres dans `checkout_templates.xml`. Ces
inherits ciblent les sélecteurs du core v17, donc les COW v16 (qui ont
des arches full-override incompatibles v17) doivent être désactivées AVANT
le chargement du data file — sinon les xpath des inherits tentent de
matcher l'arche v16 et échouent avec "cannot be located in parent view".

Les customisations CMS visuelles portées par ces COW sont perdues — à
reconstruire dans checkout_templates.xml via des inherits dédiés (sidebar
"Achat en toute confiance", stepper, reassurance, etc.).

Idempotent : UPDATE ... WHERE active=true.
"""
import logging

_logger = logging.getLogger(__name__)


CHECKOUT_COW_KEYS = (
    # Cart page
    'website_sale.cart',
    'website_sale.cart_oe_structure_website_sale_cart_1',
    'website_sale.cart_oe_structure_website_sale_cart_2',
    # Stepper
    'website_sale.wizard_checkout',
    # Address step (/shop/checkout, /shop/address)
    'website_sale.checkout',
    'website_sale.address',
    'website_sale.address_kanban',
    'website_sale.address_b2b',
    # Payment step (/shop/payment)
    'website_sale.payment',
    'website_sale.payment_delivery',
    'website_sale.payment_delivery_methods',
    'website_sale_picking.checkout_delivery',
    'website_sale.payment_oe_structure_website_sale_payment_1',
    'website_sale.payment_oe_structure_website_sale_payment_2',
    # Confirmation step (/shop/confirmation)
    'website_sale.payment_confirmation_status',
    'website_sale_picking.payment_confirmation_status',
    'website_sale.confirmation_oe_structure_website_sale_confirmation_1',
    'website_sale.confirmation_oe_structure_website_sale_confirmation_2',
    'website_sale.confirmation_oe_structure_website_sale_confirmation_3',
    # Loyalty (reduction codes / cart discount) — COW v16 avec xpath //a
    # incompatible v17 (le core v17 utilise <t t-call> au lieu de <a>)
    'website_sale_loyalty.reduction_coupon_code',
    'website_sale_loyalty.cart_discount',
)


def migrate(cr, version):
    if not version:
        return

    placeholders = ','.join(['%s'] * len(CHECKOUT_COW_KEYS))
    cr.execute(
        f"""
        UPDATE ir_ui_view
        SET active = false
        WHERE key IN ({placeholders})
          AND website_id IS NOT NULL
          AND active = true
        RETURNING id, key
        """,
        CHECKOUT_COW_KEYS,
    )
    rows = cr.fetchall()
    if rows:
        _logger.info(
            "[17.0.0.9.9 pre-migrate] Deactivated %d checkout COW(s): %s",
            len(rows), rows,
        )
    else:
        _logger.info(
            "[17.0.0.9.9 pre-migrate] No active checkout COW found — nothing to do."
        )
