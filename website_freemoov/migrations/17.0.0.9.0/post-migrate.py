# -*- coding: utf-8 -*-
"""
Post-migration: delete website-specific view copies that override module templates.

When views are edited via the Odoo website editor (CMS), Odoo creates a copy
in ir_ui_view with a website_id. These copies freeze the old HTML and prevent
module updates from taking effect.

After a v16 prod restore, v16 COW copies of parent templates (website_sale.*)
also block our v17 xpath overrides and must be removed.

This script removes those copies so the module's XML templates are used directly.
Odoo will recreate clean copies on next page visit if needed.
"""


def migrate(cr, version):
    if not version:
        return

    # Views that we manage in the module and must not have stale CMS copies.
    # NOTE: product_details_inherited is EXCLUDED — its COW copy contains CMS
    # content (sliders, "COMMANDEZ MAINTENANT", etc.) that must be preserved.
    managed_view_keys = [
        'website_freemoov.inherit_pager',
        'website_freemoov.wishlist_inherited',
        'website_freemoov.custom_text_inherited',
        'website_freemoov.share_icon_inherited',
        'website_freemoov.inherit_wishlist_button',
        'website_freemoov.inherit_compare_button',
    ]

    all_keys = managed_view_keys + [
        # v16 parent template COW copies that freeze old HTML and block v17 xpaths.
        # IMPORTANT: Do NOT include feature toggle views here (filter_products_price,
        # products_categories, sort, etc.) — those COW copies control feature ON/OFF
        # state and deleting them re-enables unwanted v17 defaults.
        'website_sale.products',
        'website_sale.products_add_to_cart',
        'website_sale.product',
        'website_sale.product_buy_now',
        # NOTE: product_comment EXCLUDED — COW copy activates reviews feature
        'website_sale.product_custom_text',
        'website_sale.product_quantity',
        'website_sale.product_share_buttons',
        'website_sale.product_picture_magnify_both',
        'website_sale.product_picture_magnify_click',
        'website_sale.product_picture_magnify_hover',
        'website_sale.shop_product_carousel',
        'website_sale.variants',
        # NOTE: tax_indication EXCLUDED — COW copy has CMS edits (TVAC + badge)
        'website_sale.alternative_products',
        'website_sale.ecom_show_extra_fields',
        'website_sale.template_header_default',
        'website_sale.add_grid_or_list_option',
    ]

    # Collect target IDs + descendants, but EXCLUDE oe_structure blocks
    # (those contain CMS content edited via the website builder)
    cr.execute("""
        WITH RECURSIVE targets AS (
            SELECT id FROM ir_ui_view
            WHERE key = ANY(%s) AND website_id IS NOT NULL
        ),
        descendants AS (
            SELECT id FROM targets
            UNION ALL
            SELECT v.id FROM ir_ui_view v
            JOIN descendants d ON v.inherit_id = d.id
            WHERE v.website_id IS NOT NULL
              AND (v.key IS NULL OR v.key NOT LIKE '%%oe_structure%%')
        )
        SELECT id FROM descendants
    """, (all_keys,))
    ids_to_delete = [row[0] for row in cr.fetchall()]

    if ids_to_delete:
        # Re-parent orphaned oe_structure children to the base view
        # before deleting the COW parents
        cr.execute("""
            UPDATE ir_ui_view oe
            SET inherit_id = (
                SELECT base.id FROM ir_ui_view base
                WHERE base.key = (
                    SELECT parent.key FROM ir_ui_view parent WHERE parent.id = oe.inherit_id
                )
                AND base.website_id IS NULL
                LIMIT 1
            )
            WHERE oe.key LIKE '%%oe_structure%%'
              AND oe.website_id IS NOT NULL
              AND oe.inherit_id = ANY(%s)
        """, (ids_to_delete,))

    # Delete iteratively: leaves first to respect FK on inherit_id
    while ids_to_delete:
        cr.execute("""
            DELETE FROM ir_ui_view
            WHERE id = ANY(%s)
            AND NOT EXISTS (
                SELECT 1 FROM ir_ui_view child
                WHERE child.inherit_id = ir_ui_view.id
                AND child.id = ANY(%s)
            )
            RETURNING id
        """, (ids_to_delete, ids_to_delete))
        deleted = [row[0] for row in cr.fetchall()]
        if not deleted:
            break
        ids_to_delete = [i for i in ids_to_delete if i not in deleted]

    # Clear asset cache so SCSS changes take effect
    cr.execute("""
        DELETE FROM ir_attachment
        WHERE url LIKE '/web/assets/%%'
    """)
