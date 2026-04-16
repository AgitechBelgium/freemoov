# -*- coding: utf-8 -*-
"""
Post-migration 17.0.0.9.3 — fixes persistants après restore dump v16 sur v17.

Traite les divergences v16→v17 qui ne peuvent pas être exprimées en XML data :

1. `website_sale.tax_indication` principal (non-COW) doit être actif pour que
   `is_view_active()` retourne True et que le t-call côté template rende.

2. Les COW `website_sale.tax_indication` (arch CMS avec TVAC + badge
   "Payez en 3x") utilisent encore les groupes v16
   `account.group_show_line_subtotals_tax_{included,excluded}` qui n'existent
   plus en v17. Le nouveau contrôle passe par
   `website.show_line_subtotals_tax_selection`.

3. Les 3 inherits d'icônes header (cart/user/wishlist) sont souvent désactivés
   dans la DB v16 (soit par CMS, soit à cause de xpath v16 obsolètes).
"""
import logging
import re

_logger = logging.getLogger(__name__)


ICON_INHERITS = (
    'website_freemoov.inherit_header_cart_link',
    'website_freemoov.inherit_user_dropdown',
    'website_freemoov.inherit_header_wishlist_link',
)

# Vues core à forcer désactivées pour matcher le comportement prod Freemoov.
# - add_grid_or_list_option : le switcher grid/list est caché, on veut du
#   grid-only sur toutes les catégories produit.
VIEWS_TO_DEACTIVATE = (
    'website_sale.add_grid_or_list_option',
)

# Arch v17-ready du template tax_indication custom (TVAC + badge payez en Nx).
# La seule différence par langue est le texte du lien (3x vs 6x) : fr_BE uses
# 3x, autres langues 6x. On le paramètre via un format string.
TAX_INDICATION_ARCH_TEMPLATE = (
    '<t active="False" t-name="website_sale.tax_indication">\n'
    '        <span t-if="website.show_line_subtotals_tax_selection == '
    "'tax_excluded'"
    '" class="h6 text-muted">\n'
    '            hors TVA\n'
    '        </span>\n'
    '        <span t-if="website.show_line_subtotals_tax_selection == '
    "'tax_included'"
    '" class="h6 text-muted" style="word-break: break-word; position: relative; z-index: 0;">'
    '\u200b<span style="font-size: 12px;"> TVAC<br/>'
    '<strong><a href="/payez-par-mois" class="btn btn-custom bg-black btn-sm" '
    'style="border-width: 1px; border-style: solid;">'
    '{pay_label}</a></strong><br/></span></span>\n'
    '    </t>'
)

GROUPS_TO_TIF = (
    (
        'groups="account.group_show_line_subtotals_tax_excluded"',
        "t-if=\"website.show_line_subtotals_tax_selection == 'tax_excluded'\"",
    ),
    (
        'groups="account.group_show_line_subtotals_tax_included"',
        "t-if=\"website.show_line_subtotals_tax_selection == 'tax_included'\"",
    ),
)


def _deactivate_views(env):
    active_views = env['ir.ui.view'].with_context(active_test=False).search([
        ('key', 'in', VIEWS_TO_DEACTIVATE),
        ('active', '=', True),
    ])
    if active_views:
        active_views.write({'active': False})
        _logger.info(
            "[17.0.0.9.3] Deactivated %d core view(s) for grid-only mode: %s",
            len(active_views), active_views.mapped('key'),
        )


def _activate_icon_inherits(env):
    disabled = env['ir.ui.view'].with_context(active_test=False).search([
        ('key', 'in', ICON_INHERITS),
        ('active', '=', False),
    ])
    if disabled:
        disabled.write({'active': True})
        _logger.info(
            "[17.0.0.9.3] Re-activated %d icon inherit view(s): %s",
            len(disabled), disabled.mapped('key'),
        )


def _activate_tax_indication_main(env):
    main_view = env.ref('website_sale.tax_indication', raise_if_not_found=False)
    if main_view and not main_view.active:
        main_view.write({'active': True})
        _logger.info(
            "[17.0.0.9.3] Activated website_sale.tax_indication main view (id=%d)",
            main_view.id,
        )


def _fix_tax_indication_cow(env):
    cows = env['ir.ui.view'].with_context(active_test=False).search([
        ('key', '=', 'website_sale.tax_indication'),
        ('website_id', '!=', False),
    ])
    if not cows:
        return

    arch_by_lang = {
        'en_US': TAX_INDICATION_ARCH_TEMPLATE.format(pay_label='Payez en 6x ou&#160;24x'),
        'fr_FR': TAX_INDICATION_ARCH_TEMPLATE.format(pay_label='Payez en 6x ou&#160;24x'),
        'fr_BE': TAX_INDICATION_ARCH_TEMPLATE.format(
            pay_label='<span style="font-size: 10px;">Payez en 3x ou&#160;24x</span>'
        ),
    }

    installed_langs = set(env['res.lang'].with_context(active_test=False).search([
        ('code', 'in', list(arch_by_lang)),
    ]).mapped('code'))

    for cow in cows:
        has_legacy_groups = any(
            old in (cow.arch_db or '') for old, _ in GROUPS_TO_TIF
        )
        needs_rewrite = has_legacy_groups or ' 6x' in (cow.arch_db or '') and cow.website_id.id == 1

        if not needs_rewrite:
            continue

        for lang, arch in arch_by_lang.items():
            if lang in installed_langs:
                cow.with_context(lang=lang).arch_db = arch

        _logger.info(
            "[17.0.0.9.3] Rewrote tax_indication COW id=%d (website_id=%s) "
            "with v17-compliant arch across langs: %s",
            cow.id, cow.website_id.id, sorted(installed_langs),
        )


def _sanitize_legacy_groups_in_cows(env):
    """Fallback: si un COW a été customisé au-delà du tax_indication standard,
    remplace juste les attributs `groups=` v16 obsolètes par leur équivalent
    `t-if=` v17, sans toucher au reste du contenu.
    """
    cows = env['ir.ui.view'].with_context(active_test=False).search([
        ('website_id', '!=', False),
        ('arch_db', 'ilike', 'group_show_line_subtotals_tax'),
    ])
    for cow in cows:
        arch = cow.arch_db or ''
        original = arch
        for old, new in GROUPS_TO_TIF:
            arch = arch.replace(old, new)
        if arch != original:
            cow.arch_db = arch
            _logger.info(
                "[17.0.0.9.3] Sanitized legacy `groups=` attrs in COW id=%d key=%r",
                cow.id, cow.key,
            )


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    _deactivate_views(env)
    _activate_icon_inherits(env)
    _activate_tax_indication_main(env)
    _fix_tax_indication_cow(env)
    _sanitize_legacy_groups_in_cows(env)

    env.registry.clear_cache()
    _logger.info("[17.0.0.9.3] Post-migrate complete — cache cleared")
