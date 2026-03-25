# -*- coding: utf-8 -*-
"""
SEO Overhaul migration — v16.0.0.3.0

1. Set seo_name on categories (shorten URLs from 130+ chars)
2. Bulk-fill website_meta_title for categories without one
3. Fix homepage_url (/ vs /home canonical mismatch)
4. Clean sitemap cache
5. Clear asset cache
6. Sync COW copies for header/footer
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info('SEO overhaul migration v16.0.0.3.0 — start')

    # ------------------------------------------------------------------
    # 1. Set seo_name on categories that don't have one
    #    JSONB: copy the name object directly (same translations).
    #    This shortens URLs from parent-path-child to just child name.
    #    Odoo auto-301-redirects old slugs when the ID matches.
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE product_public_category
        SET seo_name = name
        WHERE seo_name IS NULL
           OR seo_name::text IN ('{}', 'null', 'false')
    """)
    _logger.info('seo_name set on %d categories', cr.rowcount)

    # ------------------------------------------------------------------
    # 2. Bulk-fill website_meta_title for categories missing one
    #    JSONB: build new object by appending ' | Freemoov' to each lang key.
    #    We iterate existing language keys from the name field.
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE product_public_category
        SET website_meta_title = (
            SELECT jsonb_object_agg(
                key,
                value || ' | Freemoov'
            )
            FROM jsonb_each_text(name)
        )
        WHERE website_meta_title IS NULL
           OR website_meta_title::text IN ('{}', 'null', 'false')
    """)
    _logger.info('website_meta_title set on %d categories', cr.rowcount)

    # ------------------------------------------------------------------
    # 3. Homepage URL: keep /home (content is in homepage_template view)
    #    Canonical fix handled in seo.py _get_canonical_url() instead.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 4. Clean sitemap cache (forces regeneration with new URLs)
    # ------------------------------------------------------------------
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/sitemap-%' AND type = 'binary'")
    _logger.info('Sitemap cache cleared: %d attachments', cr.rowcount)

    # ------------------------------------------------------------------
    # 5. Clear asset cache (new CSS/JS/templates)
    # ------------------------------------------------------------------
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'")
    _logger.info('Asset cache cleared: %d attachments', cr.rowcount)

    # ------------------------------------------------------------------
    # 6. Sync COW copies for header/footer (v16 production pattern)
    # ------------------------------------------------------------------
    # Header: base 3500 -> COW 3533
    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.id = 3500 AND cow.id = 3533
          AND base.arch_db IS DISTINCT FROM cow.arch_db
    """)
    if cr.rowcount:
        _logger.info('Header COW synced (3500 -> 3533)')

    # Footer: base 3053 -> COW 3479
    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.id = 3053 AND cow.id = 3479
          AND base.arch_db IS DISTINCT FROM cow.arch_db
    """)
    if cr.rowcount:
        _logger.info('Footer COW synced (3053 -> 3479)')

    _logger.info('SEO overhaul migration v16.0.0.3.0 — done')
