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

    # Views that we manage in the module and must not have stale CMS copies
    managed_view_keys = [
        'website_freemoov.product_details_inherited',
        'website_freemoov.inherit_pager',
        'website_freemoov.wishlist_inherited',
        'website_freemoov.custom_text_inherited',
        'website_freemoov.share_icon_inherited',
        'website_freemoov.inherit_wishlist_button',
        'website_freemoov.inherit_compare_button',
    ]

    for key in managed_view_keys:
        cr.execute("""
            DELETE FROM ir_ui_view
            WHERE key = %s
            AND website_id IS NOT NULL
        """, (key,))

    # v16 parent template COW copies that block v17 xpaths after prod restore
    v16_parent_keys = [
        'website_sale.products',
        'website_sale.products_add_to_cart',
        'website_sale.product',
        'website_sale.product_buy_now',
        'website_sale.product_comment',
        'website_sale.product_custom_text',
        'website_sale.product_quantity',
        'website_sale.product_share_buttons',
        'website_sale.product_picture_magnify_both',
        'website_sale.product_picture_magnify_click',
        'website_sale.product_picture_magnify_hover',
        'website_sale.shop_product_carousel',
        'website_sale.variants',
        'website_sale.tax_indication',
        'website_sale.alternative_products',
        'website_sale.ecom_show_extra_fields',
        'website_sale.template_header_default',
        'website_sale.add_grid_or_list_option',
        'website_sale.products_design_card',
        'website_sale.products_design_grid',
        'website_sale.products_design_thumbs',
        'website_sale.products_thumb_2_3',
        'website_sale.products_thumb_4_3',
        'website_sale.products_thumb_4_5',
        'website_sale.products_thumb_cover',
        'website_sale.products_list_view',
        'website_sale.products_description',
        'website_sale.products_categories',
        'website_sale.products_categories_top',
        'website_sale.products_attributes',
        'website_sale.products_attributes_top',
        'website_sale.products_fiscal_position',
        'website_sale.sort',
        'website_sale.carousel_product_indicators_bottom',
        'website_sale.carousel_product_indicators_left',
        'website_sale.product_variants',
        'website_sale.filter_products_price',
        'website_sale.accept_terms_and_conditions',
        'website_sale.suggested_products_list',
        'website_sale.wizard_checkout',
    ]

    for key in v16_parent_keys:
        cr.execute("""
            DELETE FROM ir_ui_view
            WHERE key = %s
            AND website_id IS NOT NULL
        """, (key,))

    # Clear asset cache so SCSS changes take effect
    cr.execute("""
        DELETE FROM ir_attachment
        WHERE url LIKE '/web/assets/%%'
    """)
