# -*- coding: utf-8 -*-
"""Post-migration 17.0.1.0.3 — rename the FLOA payment.method on existing
installs so the checkout label reads "Floa Pay (3x sans frais)" instead
of the bare "FLOA Pay".

The data file ships the new name for fresh installs but is noupdate=1,
so we have to rewrite the record by hand here. We only rename when the
current name still matches the legacy value to avoid stomping a custom
admin-side rename.
"""
import logging

_logger = logging.getLogger(__name__)

LEGACY_NAME = 'FLOA Pay'
NEW_NAME = 'Floa Pay (3x sans frais)'


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    method = env.ref('payment_floa.payment_method_floa', raise_if_not_found=False)
    if not method:
        _logger.info("[17.0.1.0.3] payment_method_floa not found, skipping rename")
        return

    if method.name == NEW_NAME:
        _logger.info("[17.0.1.0.3] FLOA payment.method name already up to date")
        return

    if method.name != LEGACY_NAME:
        _logger.info(
            "[17.0.1.0.3] FLOA payment.method has a custom name %r, skipping rename",
            method.name,
        )
        return

    method.name = NEW_NAME
    _logger.info(
        "[17.0.1.0.3] Renamed FLOA payment.method id=%d from %r to %r",
        method.id, LEGACY_NAME, NEW_NAME,
    )
