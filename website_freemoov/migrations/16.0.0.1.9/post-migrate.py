import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """v16.0.0.1.9 — footer redesign: trust bar, tagline, copyright, dark theme."""
    _logger.info("Footer redesign migration v16.0.0.1.9 — start")

    # Sync footer COW copy (base → website-specific)
    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.key = 'website_freemoov.footer'
          AND base.website_id IS NULL
          AND cow.key = 'website_freemoov.footer'
          AND cow.website_id IS NOT NULL
          AND base.arch_db IS DISTINCT FROM cow.arch_db
    """)
    if cr.rowcount:
        _logger.info("Footer COW synced (%d copies)", cr.rowcount)

    # Sync copyright bar COW copy
    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.key = 'website_freemoov.footer_copyright_company_name_inherited_portal'
          AND base.website_id IS NULL
          AND cow.key = 'website_freemoov.footer_copyright_company_name_inherited_portal'
          AND cow.website_id IS NOT NULL
          AND base.arch_db IS DISTINCT FROM cow.arch_db
    """)
    if cr.rowcount:
        _logger.info("Copyright bar COW synced (%d copies)", cr.rowcount)

    # Clear asset cache
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'")
    _logger.info("Asset cache cleared: %d attachments", cr.rowcount)

    _logger.info("Footer redesign migration v16.0.0.1.9 — done")
