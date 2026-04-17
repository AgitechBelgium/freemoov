import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Footer + Cart/Checkout redesign v2.0: clear assets, sync footer COW copies."""
    _logger.info("Running post-migration for v16.0.0.2.0...")

    # Clear asset bundles
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';")
    _logger.info("Asset bundles cleared.")

    # Sync footer template COW copy (base → website-specific)
    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.key = 'website_freemoov.footer'
          AND base.website_id IS NULL
          AND cow.key = 'website_freemoov.footer'
          AND cow.website_id IS NOT NULL;
    """)
    rows = cr.rowcount
    _logger.info("Footer COW copy synced (%s rows).", rows)

    # Sync copyright template COW copy
    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.key = 'website_freemoov.footer_copyright_company_name_inherited_portal'
          AND base.website_id IS NULL
          AND cow.key = 'website_freemoov.footer_copyright_company_name_inherited_portal'
          AND cow.website_id IS NOT NULL;
    """)
    rows = cr.rowcount
    _logger.info("Copyright COW copy synced (%s rows).", rows)

    # Disable Odoo brand promotion badge in footer
    cr.execute("""
        UPDATE ir_ui_view SET active = False
        WHERE key IN ('website.brand_promotion', 'website_sale.brand_promotion',
                      'website.show_website_info')
          AND active = True;
    """)
    if cr.rowcount:
        _logger.info("Odoo brand badges disabled (%s views).", cr.rowcount)

    _logger.info("Post-migration v16.0.0.2.0 complete.")
