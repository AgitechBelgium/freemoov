import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Cart/Checkout Shopify-level redesign v2.1: clear assets."""
    _logger.info("Running post-migration for v16.0.0.2.1...")
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';")
    _logger.info("Asset bundles cleared for v16.0.0.2.1.")
