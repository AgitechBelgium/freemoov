# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Clear asset cache after SCSS changes (shop card improvements)."""
    _logger.info("Clearing asset cache for shop SCSS updates...")
    cr.execute("DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'")
    _logger.info("Asset cache cleared.")
