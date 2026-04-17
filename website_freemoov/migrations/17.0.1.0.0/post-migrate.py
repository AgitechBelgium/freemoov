# -*- coding: utf-8 -*-
"""
Post-migration 17.0.1.0.0 — restore des pertes silencieuses v16→v17
détectées par l'audit prod-ISO.

Corrige 4 catégories de pertes qui ne sont pas de simples counts :

1. ir.config_parameter : 4 settings critiques perdus par l'upgrade Odoo SA.
2. ir.sequence : la séquence `account.reconcile` (rapprochements bancaires)
   a été supprimée par la migration.
3. res.partner : 50 partners (dont l'Administrator) ont été archivés
   automatiquement par le cleanup post-upgrade. À réactiver pour maintenir
   la parité data avec prod v16.
4. mail.template : 3 templates critiques ("Settings: User Reset Password",
   "Account Invoice Extract Notification", "Repair: Quotation") ont
   changé de xml_id en v17. Géré par un script séparé qui dumpe depuis
   prod (non inclus ici car body_html volumineux).

Opération idempotente — relance sans effet si déjà appliqué.
"""
import logging

_logger = logging.getLogger(__name__)


# ir.config_parameter critiques à restaurer (hors staging-specific).
CRITICAL_PARAMS = {
    'account.show_line_subtotals_tax_selection': 'tax_included',
    'sale.default_deposit_product_id': '529',
    'sale.use_quotation_validity_days': 'True',
    'spreadsheet_edition.revisions_limit_days': '60',
}


# IDs des partners archivés par le cleanup v17 mais actifs sur prod v16.
# Liste calculée via `comm -12` entre ir_partner actifs prod et archivés staging.
# Inclut Administrator (3524), clients individuels, et doublons notables.
PARTNERS_TO_REACTIVATE = [
    3524, 5100, 5321, 5366, 5367, 5368, 5369, 5370, 5371, 5403,
    14659, 14660, 14661, 14662, 14663, 14789, 14913, 14914, 14915,
    14916, 14917, 14918, 14919, 14920, 14921, 14922, 14923, 14924,
    14925, 14926, 14927, 14928, 14929, 14985, 14986, 14987, 14988,
    14989, 14990, 14991, 14992, 14993, 14994, 14995, 14996, 14997,
    15056, 15974, 15977, 15986,
]


def _restore_config_parameters(env):
    """Recrée les 4 ir.config_parameter critiques perdus par l'upgrade."""
    Param = env['ir.config_parameter'].sudo()
    restored = []
    for key, value in CRITICAL_PARAMS.items():
        current = Param.get_param(key)
        if current == value:
            continue
        Param.set_param(key, value)
        restored.append((key, current or '(missing)', value))

    if restored:
        _logger.info(
            "[17.0.1.0.0] Restored %d ir.config_parameter(s):", len(restored),
        )
        for key, old, new in restored:
            _logger.info("  - %s: %r → %r", key, old, new)
    else:
        _logger.info("[17.0.1.0.0] All critical config params already set.")


def _restore_reconcile_sequence(env):
    """Recrée la séquence account.reconcile si absente.
    Utilisée par les rapprochements bancaires pour la numérotation."""
    Seq = env['ir.sequence'].sudo()
    existing = Seq.search([('code', '=', 'account.reconcile')], limit=1)
    if existing:
        _logger.info(
            "[17.0.1.0.0] Sequence account.reconcile already present (id=%d)",
            existing.id,
        )
        return

    new_seq = Seq.create({
        'name': 'Account reconcile sequence',
        'code': 'account.reconcile',
        'prefix': 'A',
        'padding': 0,
        'number_next': 1,
        'number_increment': 1,
        'implementation': 'standard',
        'active': True,
    })
    _logger.info(
        "[17.0.1.0.0] Created sequence account.reconcile (id=%d, prefix=A)",
        new_seq.id,
    )


def _reactivate_archived_sequences(env):
    """Certaines séquences (ex: repair.order) ont été archivées par l'upgrade.
    Réactive toutes les séquences core qui devraient être actives."""
    Seq = env['ir.sequence'].with_context(active_test=False).sudo()
    # Codes de séquences core à garantir actives (basé sur diff prod/staging).
    core_codes = ('repair.order',)
    archived = Seq.search([('code', 'in', core_codes), ('active', '=', False)])
    if archived:
        archived.write({'active': True})
        _logger.info(
            "[17.0.1.0.0] Reactivated %d archived ir.sequence(s): %s",
            len(archived), archived.mapped('code'),
        )


def _reactivate_partners(env):
    """Réactive les 50 partners archivés par le cleanup post-upgrade.
    Préserve la parité avec prod v16 (dont l'Administrator = id 3524)."""
    Partner = env['res.partner'].with_context(active_test=False).sudo()
    archived = Partner.search([
        ('id', 'in', PARTNERS_TO_REACTIVATE),
        ('active', '=', False),
    ])
    if not archived:
        _logger.info(
            "[17.0.1.0.0] No partners to reactivate (all already active)."
        )
        return

    archived.write({'active': True})
    _logger.info(
        "[17.0.1.0.0] Reactivated %d res_partner(s) archived by v17 upgrade: %s",
        len(archived), archived.ids,
    )


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    _restore_config_parameters(env)
    _restore_reconcile_sequence(env)
    _reactivate_archived_sequences(env)
    _reactivate_partners(env)

    env.registry.clear_cache()
    _logger.info("[17.0.1.0.0] Post-migrate complete — cache cleared")
