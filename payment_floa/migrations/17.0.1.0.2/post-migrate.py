# -*- coding: utf-8 -*-
"""Post-migration 17.0.1.0.2 — populate the FLOA payment.method image.

The payment.method record is loaded with noupdate="1" to protect any
admin-side rename or activation toggle, but that means new fields added
to the data XML never reach existing installs. The checkout therefore
shows the broken-image placeholder next to "FLOA Pay" instead of the
brand logo. This migration loads the bundled icon from disk and writes
it onto the existing record once.

Idempotent: if the image is already populated and matches the bundled
asset, the write is skipped.
"""
import base64
import logging
import os

_logger = logging.getLogger(__name__)


def _load_icon_b64():
    here = os.path.dirname(__file__)
    icon_path = os.path.normpath(
        os.path.join(here, '..', '..', 'static', 'description', 'icon.png')
    )
    if not os.path.isfile(icon_path):
        _logger.warning("[17.0.1.0.2] FLOA icon not found at %s", icon_path)
        return None
    with open(icon_path, 'rb') as fh:
        return base64.b64encode(fh.read())


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    method = env.ref('payment_floa.payment_method_floa', raise_if_not_found=False)
    if not method:
        _logger.info("[17.0.1.0.2] payment_method_floa not found, skipping image seed")
        return

    icon_b64 = _load_icon_b64()
    if not icon_b64:
        return

    # Compare existing image (also base64) to avoid pointless writes.
    current = method.image or b''
    if isinstance(current, str):
        current = current.encode()
    if current == icon_b64:
        _logger.info("[17.0.1.0.2] FLOA payment.method image already up to date")
        return

    method.image = icon_b64
    _logger.info(
        "[17.0.1.0.2] Set FLOA payment.method image (%d bytes b64) on record id=%d",
        len(icon_b64), method.id,
    )
