import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Clear asset bundles to force reload of updated CSS/JS (CLS fixes v1.7)."""
    _logger.info("Clearing asset bundles for v16.0.0.1.7...")
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';")
    _logger.info("Asset bundles cleared.")
