# -*- coding: utf-8 -*-
"""Post-migration 17.0.1.1.4 — drop the legacy "Payez en 3x ou 24x" badge
from the website_sale.tax_indication COW.

Context: migration 17.0.0.9.3 had to rewrite the tax_indication COW after
the v16->v17 dump restore (legacy account.group_show_line_subtotals_tax_*
groups no longer exist in v17). At the time it embedded a "/payez-par-mois"
button next to "TVAC" because no real installment widget was wired in.

Now that payment_floa is live and renders its own dynamic widget below the
price, that legacy button is a duplicate and confuses customers (it is
visible right next to the real Floa simulator). This migration strips just
the <strong><a>...</a></strong><br/> block from the COW arch, keeping the
TVAC label and the surrounding tax_excluded/tax_included branches intact.

Idempotent: re-running on a COW that no longer contains the badge is a no-op.
"""
import json
import logging
import re

_logger = logging.getLogger(__name__)


# Match the legacy badge regardless of label localization (3x/4x/6x/24x):
# any <strong><a href="/payez-par-mois" ...>...</a></strong> immediately
# followed by an optional <br/>. The DOTALL flag is not needed because the
# anchor is single-line as injected by 17.0.0.9.3.
LEGACY_BADGE_RE = re.compile(
    r'<strong>\s*<a href="/payez-par-mois"[^>]*>.*?</a>\s*</strong>\s*(<br\s*/?>)?',
    re.IGNORECASE,
)


def _strip_badge(html):
    """Return (new_html, removed_count). Strips every legacy badge occurrence."""
    if not html or '/payez-par-mois' not in html:
        return html, 0
    new_html, count = LEGACY_BADGE_RE.subn('', html)
    return new_html, count


def _patch_tax_indication_cows(cr):
    cr.execute("""
        SELECT id, arch_db FROM ir_ui_view
         WHERE key = 'website_sale.tax_indication'
           AND website_id IS NOT NULL
           AND arch_db::text LIKE '%/payez-par-mois%'
    """)
    rows = cr.fetchall()
    if not rows:
        _logger.info("[17.0.1.1.4] No tax_indication COW with legacy badge found")
        return

    for view_id, arch in rows:
        if not isinstance(arch, dict):
            # Older Odoo storage: arch is a single string, not jsonb dict.
            new_arch, count = _strip_badge(arch)
            if count:
                cr.execute(
                    "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                    (new_arch, view_id),
                )
                _logger.info(
                    "[17.0.1.1.4] Stripped %d legacy badge(s) from tax_indication "
                    "COW id=%d (single-lang arch)",
                    count, view_id,
                )
            continue

        modified = False
        total = 0
        for lang, value in list(arch.items()):
            new_value, count = _strip_badge(value)
            if count:
                arch[lang] = new_value
                modified = True
                total += count

        if modified:
            cr.execute(
                "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                (json.dumps(arch), view_id),
            )
            _logger.info(
                "[17.0.1.1.4] Stripped %d legacy badge occurrence(s) from "
                "tax_indication COW id=%d across langs %s",
                total, view_id, sorted(arch.keys()),
            )


def migrate(cr, version):
    if not version:
        return
    _patch_tax_indication_cows(cr)
    _logger.info("[17.0.1.1.4] Post-migrate complete")
