# -*- coding: utf-8 -*-
"""
Post-migration executed APRÈS le chargement des modèles et vues v17.

Tente de réactiver les vues qui avaient été désactivées par le pre-migrate
17.0.0.0.9 (vues orphelines référençant seo_*, gmc_*, faq_*, etc.).

Maintenant que les modules suivants sont portés et installés :
  - website_freemoov (seo.py, product_faq.py)
  - google_merchant_center (gmc_* fields)
les champs existent à nouveau → les vues peuvent redevenir valides.

Odoo va re-valider les vues au prochain chargement — si une vue est
encore invalide (ex: vue custom user-created référant un champ sur un
mauvais modèle), Odoo la re-désactivera automatiquement avec un warning.
"""
import logging

_logger = logging.getLogger(__name__)


ORPHAN_V16_FIELDS = (
    'seo_intro', 'seo_outro', 'seo_content', 'seo_h1',
    'seo_meta_title_extra', 'seo_meta_description_extra',
    'faq_ids', 'product_faq_ids', 'editorial_review', 'video_url',
    'gmc_enabled', 'gmc_sync_status', 'gmc_category', 'gmc_last_sync',
    'gmc_last_error', 'gmc_feed_status', 'gmc_offer_id', 'gmc_gtin',
    'gmc_brand', 'gmc_product_type',
    'gmc_custom_label_0', 'gmc_custom_label_1', 'gmc_custom_label_2',
    'gmc_custom_label_3', 'gmc_custom_label_4',
)


def migrate(cr, version):
    if not version:
        return

    like_clauses = " OR ".join(
        "arch_db::text LIKE %s" for _ in ORPHAN_V16_FIELDS
    )
    params = [f"%{field}%" for field in ORPHAN_V16_FIELDS]

    cr.execute(
        f"""
        SELECT id, name, model, key
          FROM ir_ui_view
         WHERE active = false
           AND arch_db IS NOT NULL
           AND ({like_clauses})
        """,
        params,
    )
    rows = cr.fetchall()

    if not rows:
        _logger.info(
            "[17.0.0.9.2 post-migrate] Aucune vue orpheline à réactiver."
        )
        return

    _logger.info(
        "[17.0.0.9.2 post-migrate] Tentative de réactivation de %d vue(s) :",
        len(rows),
    )
    for row in rows:
        _logger.info("  - id=%s name=%r model=%r key=%r", *row)

    cr.execute(
        f"""
        UPDATE ir_ui_view
           SET active = true
         WHERE active = false
           AND arch_db IS NOT NULL
           AND ({like_clauses})
        """,
        params,
    )
    _logger.info(
        "[17.0.0.9.2 post-migrate] %d vue(s) marquée(s) active. "
        "Odoo les re-validera au prochain chargement (invalid → re-disabled auto).",
        cr.rowcount,
    )
