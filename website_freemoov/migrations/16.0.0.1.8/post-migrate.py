import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Header redesign v1.8: clear assets + sync COW copies."""
    _logger.info("Clearing asset bundles for v16.0.0.1.8...")
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';")

    # Sync COW copies of header_freemoov_two with updated base template
    # arch_db is JSONB in Odoo 16, so copy directly in SQL
    cr.execute("""
        UPDATE ir_ui_view AS cow
        SET arch_db = base.arch_db
        FROM ir_ui_view AS base
        WHERE base.key = 'website_freemoov.header_freemoov_two'
        AND base.website_id IS NULL
        AND cow.key = 'website_freemoov.header_freemoov_two'
        AND cow.website_id IS NOT NULL
    """)
    _logger.info("COW copies of header_freemoov_two synced with base template.")

    _logger.info("Header redesign migration complete.")
