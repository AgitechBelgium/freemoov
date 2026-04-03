# -*- coding: utf-8 -*-
"""
v16.0.0.5.2 — Add review to category listings, aggregateRating to variants.

1. Clear caches
2. Sync COW header/footer
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info('Migration v16.0.0.5.2 — start')

    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'")
    _logger.info('Asset cache cleared: %d attachments', cr.rowcount)

    cr.execute(
        "DELETE FROM ir_attachment WHERE url LIKE '/sitemap-%' AND type = 'binary'"
    )
    _logger.info('Sitemap cache cleared: %d attachments', cr.rowcount)

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

    _logger.info('Migration v16.0.0.5.2 — done')
