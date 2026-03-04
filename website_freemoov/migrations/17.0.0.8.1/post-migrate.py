# -*- coding: utf-8 -*-
"""
Post-migration: delete website-specific view copies that override module templates.

When views are edited via the Odoo website editor (CMS), Odoo creates a copy
in ir_ui_view with a website_id. These copies freeze the old HTML and prevent
module updates from taking effect.

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

    # Clear asset cache so SCSS changes take effect
    cr.execute("""
        DELETE FROM ir_attachment
        WHERE url LIKE '/web/assets/%%'
    """)
