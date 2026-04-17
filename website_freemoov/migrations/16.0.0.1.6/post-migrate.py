import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Clear asset bundles to force reload of updated CSS (CLS fixes)."""
    _logger.info("Clearing asset bundles for v16.0.0.1.6...")
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';")
    _logger.info("Asset bundles cleared.")
