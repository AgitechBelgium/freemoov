# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Clear asset cache after XML view changes."""
    _logger.info("Clearing asset cache...")
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'")
    _logger.info("Asset cache cleared.")
