# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    fm_maintenance_banner_active = fields.Boolean(
        string="Afficher le bandeau d'avertissement",
        config_parameter="website_freemoov.maintenance_banner_active",
    )
    fm_maintenance_mode_active = fields.Boolean(
        string="Activer la page de maintenance",
        config_parameter="website_freemoov.maintenance_mode_active",
    )
    fm_maintenance_start_datetime = fields.Datetime(
        string="Début de la maintenance",
        config_parameter="website_freemoov.maintenance_start_datetime",
    )
    fm_maintenance_message = fields.Char(
        string="Message personnalisé (optionnel)",
        config_parameter="website_freemoov.maintenance_message",
    )
