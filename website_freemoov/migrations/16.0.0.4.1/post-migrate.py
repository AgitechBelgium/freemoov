# -*- coding: utf-8 -*-
"""
v16.0.0.4.1 — Auto-unpublish archived products, clear caches, sync COW.

Also forces XML reload (seo_strip_microdata template was added in
previous commit but never loaded because version didn't change).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info('Migration v16.0.0.4.1 — start')

    # ------------------------------------------------------------------
    # 1. Unpublish all archived products still marked as published
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE product_template
        SET is_published = False
        WHERE active = False
          AND is_published = True
    """)
    _logger.info('Unpublished %d archived products', cr.rowcount)

    # ------------------------------------------------------------------
    # 2. Clear asset cache
    # ------------------------------------------------------------------
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'")
    _logger.info('Asset cache cleared: %d attachments', cr.rowcount)

    # ------------------------------------------------------------------
    # 3. Clear sitemap cache
    # ------------------------------------------------------------------
    cr.execute(
        "DELETE FROM ir_attachment WHERE url LIKE '/sitemap-%' AND type = 'binary'"
    )
    _logger.info('Sitemap cache cleared: %d attachments', cr.rowcount)

    # ------------------------------------------------------------------
    # 4. Sync COW copies for header/footer
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

    _logger.info('Migration v16.0.0.4.1 — done')
