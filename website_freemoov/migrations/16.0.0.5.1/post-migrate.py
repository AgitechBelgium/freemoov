# -*- coding: utf-8 -*-
"""
v16.0.0.5.1 — Rich snippets & merchant listings fixes.

1. Clear caches (assets, sitemap)
2. Sync COW header/footer
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info('Migration v16.0.0.5.1 — start')

    # ------------------------------------------------------------------
    # 1. Clear asset + sitemap caches
    # ------------------------------------------------------------------
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'")
    _logger.info('Asset cache cleared: %d attachments', cr.rowcount)

    cr.execute(
        "DELETE FROM ir_attachment WHERE url LIKE '/sitemap-%' AND type = 'binary'"
    )
    _logger.info('Sitemap cache cleared: %d attachments', cr.rowcount)

    # ------------------------------------------------------------------
    # 2. Sync COW header (3500 -> 3533) + footer (3053 -> 3479)
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.id = 3500 AND cow.id = 3533
          AND base.arch_db IS DISTINCT FROM cow.arch_db
    """)
    if cr.rowcount:
        _logger.info('Header COW synced')

    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.id = 3053 AND cow.id = 3479
          AND base.arch_db IS DISTINCT FROM cow.arch_db
    """)
    if cr.rowcount:
        _logger.info('Footer COW synced')

    # ------------------------------------------------------------------
    # 3. Unpublish test product (no image, pollutes merchant listings)
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE product_template SET is_published = false
        WHERE id = 1067 AND name->>'en_US' = 'Test eCommerce'
    """)
    if cr.rowcount:
        _logger.info('Unpublished test product id=1067')

    _logger.info('Migration v16.0.0.5.1 — done')
