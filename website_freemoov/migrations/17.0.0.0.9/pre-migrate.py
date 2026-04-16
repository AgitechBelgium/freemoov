# -*- coding: utf-8 -*-
"""
Pre-migration script executed BEFORE v17 views and models are loaded.

Rôle:
1. Cleanup badge_extra_price_fix view (forcer la recréation).
2. Désactiver les vues orphelines créées en v16 par des modules non encore portés
   en v17 (notamment le module SEO qui ajoutait seo_intro, seo_outro, faq_ids, etc.
   sur product.public.category et product.template). Ces vues persistent en DB
   après l'upgrade et bloquent le chargement des vues v17 du module website_freemoov
   lors de la validation croisée.

   Les vues sont DÉSACTIVÉES (active=false), pas supprimées — elles pourront être
   réactivées une fois le module SEO porté en v17.
"""
import logging

_logger = logging.getLogger(__name__)


# Champs ajoutés par des modules v16 non encore portés en v17 :
#   - module SEO (models/seo.py en prod)     → seo_*
#   - module google_merchant_center          → gmc_*
#   - module product_faq                     → faq_*
# Toute vue qui les référence bloquera le load Odoo tant que ces modules
# ne sont pas portés (cf. docs/PORTING_CHECKLIST.md Lots 3 et 4).
ORPHAN_V16_FIELDS = (
    # SEO module
    'seo_intro',
    'seo_outro',
    'seo_content',
    'seo_h1',
    'seo_meta_title_extra',
    'seo_meta_description_extra',
    # FAQ
    'faq_ids',
    'product_faq_ids',
    'editorial_review',
    'video_url',
    # Google Merchant Center
    'gmc_enabled',
    'gmc_sync_status',
    'gmc_category',
    'gmc_last_sync',
    'gmc_last_error',
    'gmc_feed_status',
    'gmc_offer_id',
    'gmc_gtin',
    'gmc_brand',
    'gmc_product_type',
    'gmc_custom_label_0',
    'gmc_custom_label_1',
    'gmc_custom_label_2',
    'gmc_custom_label_3',
    'gmc_custom_label_4',
)


def migrate(cr, version):
    if not version:
        return

    # --- 1. Cleanup badge_extra_price_fix (existant) ---
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE key = 'website_freemoov.badge_extra_price_fix'
    """)
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'website_freemoov'
          AND name = 'badge_extra_price_fix'
    """)

    # --- 2. Désactivation des vues orphelines référençant les champs SEO v16 ---
    like_clauses = " OR ".join(
        "arch_db::text LIKE %s" for _ in ORPHAN_V16_FIELDS
    )
    params = [f"%{field}%" for field in ORPHAN_V16_FIELDS]

    cr.execute(
        f"""
        SELECT id, name, model, key
          FROM ir_ui_view
         WHERE active = true
           AND arch_db IS NOT NULL
           AND ({like_clauses})
        """,
        params,
    )
    rows = cr.fetchall()

    if rows:
        _logger.warning(
            "[17.0.0.0.9 pre-migrate] Désactivation de %d vue(s) orpheline(s) "
            "référençant des champs SEO v16 non portés:",
            len(rows),
        )
        for row in rows:
            _logger.warning("  - id=%s name=%r model=%r key=%r", *row)

        cr.execute(
            f"""
            UPDATE ir_ui_view
               SET active = false
             WHERE active = true
               AND arch_db IS NOT NULL
               AND ({like_clauses})
            """,
            params,
        )
        _logger.warning(
            "[17.0.0.0.9 pre-migrate] %d vue(s) désactivée(s) avec succès.",
            cr.rowcount,
        )
    else:
        _logger.info(
            "[17.0.0.0.9 pre-migrate] Aucune vue orpheline SEO à désactiver."
        )
