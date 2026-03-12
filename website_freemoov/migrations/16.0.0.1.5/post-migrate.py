import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Clear asset bundles to force reload of updated CSS (feather font-display, homepage styles)."""
    _logger.info("Clearing asset bundles for v16.0.0.1.5...")
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';")
    _logger.info("Asset bundles cleared.")
