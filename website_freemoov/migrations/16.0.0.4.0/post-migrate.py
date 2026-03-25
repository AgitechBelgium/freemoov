# -*- coding: utf-8 -*-
"""
SEO + UX Overhaul migration — v16.0.0.4.0

1. Clear asset + sitemap cache
2. Sync COW copies for header/footer
3. Activate product_comment toggle (native Odoo reviews)
4. Set website_meta_title on published products without one
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info('SEO+UX overhaul migration v16.0.0.4.0 — start')

    # ------------------------------------------------------------------
    # 1. Clear asset cache (new SCSS/templates)
    # ------------------------------------------------------------------
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'")
    _logger.info('Asset cache cleared: %d attachments', cr.rowcount)

    # ------------------------------------------------------------------
    # 2. Clear sitemap cache
    # ------------------------------------------------------------------
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/sitemap-%' AND type = 'binary'")
    _logger.info('Sitemap cache cleared: %d attachments', cr.rowcount)

    # ------------------------------------------------------------------
    # 3. Sync COW copies for header/footer
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.id = 3500 AND cow.id = 3533
          AND base.arch_db IS DISTINCT FROM cow.arch_db
    """)
    if cr.rowcount:
        _logger.info('Header COW synced (3500 -> 3533)')

    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.id = 3053 AND cow.id = 3479
          AND base.arch_db IS DISTINCT FROM cow.arch_db
    """)
    if cr.rowcount:
        _logger.info('Footer COW synced (3053 -> 3479)')

    # ------------------------------------------------------------------
    # 4. Activate product_comment toggle (native Odoo reviews)
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE ir_ui_view
        SET active = True
        WHERE key = 'website_sale.product_comment'
          AND active = False
    """)
    if cr.rowcount:
        _logger.info('Activated product_comment toggle (%d views)', cr.rowcount)

    # ------------------------------------------------------------------
    # 5. Set website_meta_title on published products without one
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE product_template
        SET website_meta_title = (
            SELECT jsonb_object_agg(key, value || ' | Freemoov')
            FROM jsonb_each_text(name)
        )
        WHERE is_published = True
          AND (website_meta_title IS NULL
               OR website_meta_title::text IN ('{}', 'null', 'false'))
    """)
    _logger.info('Product meta titles set: %d products', cr.rowcount)

    # ------------------------------------------------------------------
    # 6. Add | Freemoov to existing meta titles that don't have it
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE product_template
        SET website_meta_title = (
            SELECT jsonb_object_agg(key, value || ' | Freemoov')
            FROM jsonb_each_text(website_meta_title)
        )
        WHERE is_published = True
          AND website_meta_title IS NOT NULL
          AND website_meta_title::text NOT LIKE '%Freemoov%'
    """)
    _logger.info('Product meta titles suffixed: %d products', cr.rowcount)

    _logger.info('SEO+UX overhaul migration v16.0.0.4.0 — done')
