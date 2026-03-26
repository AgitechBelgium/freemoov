# -*- coding: utf-8 -*-
"""
v16.0.0.5.0 — ProductGroup JSON-LD, category link fix, cookie-policy redirect.

1. Clear all caches (assets, sitemap, QWeb)
2. Sync COW header/footer
3. Add /cookie-policy → /privacy-policy redirect
4. Ensure website.domain is NULL (prevent noindex from domain mismatch)
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info('Migration v16.0.0.5.0 — start')

    # ------------------------------------------------------------------
    # 1. Clear asset + sitemap + QWeb caches
    # ------------------------------------------------------------------
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'")
    _logger.info('Asset cache cleared: %d attachments', cr.rowcount)

    cr.execute(
        "DELETE FROM ir_attachment WHERE url LIKE '/sitemap-%' AND type = 'binary'"
    )
    _logger.info('Sitemap cache cleared: %d attachments', cr.rowcount)

    # Clear QWeb page cache (forces re-render, fixes stale noindex)
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/xmlcache/%'")

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
    # 3. Add /cookie-policy → /privacy-policy redirect
    # ------------------------------------------------------------------
    cr.execute("""
        INSERT INTO website_rewrite (name, url_from, url_to, redirect_type, active, website_id)
        SELECT 'Cookie policy redirect', '/cookie-policy', '/privacy-policy', '301', True, 1
        WHERE NOT EXISTS (
            SELECT 1 FROM website_rewrite WHERE url_from = '/cookie-policy'
        )
    """)
    if cr.rowcount:
        _logger.info('Added /cookie-policy → /privacy-policy redirect')

    # ------------------------------------------------------------------
    # 4. Ensure website.domain is NULL (prevent noindex on Odoo.sh)
    # ------------------------------------------------------------------
    cr.execute("UPDATE website SET domain = NULL WHERE domain IS NOT NULL")
    if cr.rowcount:
        _logger.info('Cleared website.domain to prevent noindex')

    _logger.info('Migration v16.0.0.5.0 — done')
