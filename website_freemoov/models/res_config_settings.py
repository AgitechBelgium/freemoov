# -*- coding: utf-8 -*-
from odoo import fields, models


_BOOL_PARAMS = (
    "website_freemoov.maintenance_banner_active",
    "website_freemoov.maintenance_mode_active",
)


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

    def set_values(self):
        # Odoo's config_parameter mechanism stores booleans as repr(value),
        # so False becomes the string "False". default_get then does
        # bool(value) which is True for any non-empty string — the checkbox
        # appears checked even when the user unticked it. Normalize to an
        # empty string for falsy values so bool("") is False.
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        for key in _BOOL_PARAMS:
            if ICP.get_param(key) == "False":
                ICP.set_param(key, "")
