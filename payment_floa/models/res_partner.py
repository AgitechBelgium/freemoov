# -*- coding: utf-8 -*-

import re
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    floa_birth_date = fields.Date(
        string="Date de naissance (FLOA)",
        help="Date de naissance — requise par FLOA pour l'analyse de crédit "
             "du paiement fractionné. Le client doit être majeur.",
    )
    floa_birth_country_id = fields.Many2one(
        'res.country',
        string="Pays de naissance (FLOA)",
        help="Pays de naissance du client — transmis à FLOA pour la "
             "vérification d'identité. Par défaut : Belgique.",
    )
    floa_national_number = fields.Char(
        string="Numéro national (FLOA)",
        help="Numéro de Registre national (NRN) ou BIS belge — recommandé par "
             "FLOA pour fiabiliser l'analyse de crédit. Format : 11 chiffres.",
    )

    @api.constrains('floa_national_number')
    def _check_floa_national_number(self):
        for partner in self:
            if not partner.floa_national_number:
                continue
            cleaned = re.sub(r'[\s.\-/]', '', partner.floa_national_number)
            if not re.match(r'^\d{11}$', cleaned):
                raise ValidationError(
                    _("Le numéro national belge doit contenir exactement 11 chiffres.")
                )

    @api.constrains('floa_birth_date')
    def _check_floa_birth_date(self):
        today = date.today()
        for partner in self:
            if not partner.floa_birth_date:
                continue
            if partner.floa_birth_date >= today:
                raise ValidationError(_("La date de naissance doit être dans le passé."))
            age = (today - partner.floa_birth_date).days // 365
            if age < 18:
                raise ValidationError(
                    _("Le paiement fractionné FLOA est réservé aux personnes majeures (18 ans et plus).")
                )
            if age > 120:
                raise ValidationError(_("Date de naissance invalide."))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _floa_get_national_number(self):
        """Return the cleaned national number (digits only) or empty string."""
        self.ensure_one()
        if not self.floa_national_number:
            return ''
        return re.sub(r'[\s.\-/]', '', self.floa_national_number)

    def _floa_has_mandatory_info(self):
        """Return True when the partner has every field required by FLOA.

        Mandatory fields per FLOA spec for BC3XFBE:
          - firstName / lastName (from partner.name)
          - email
          - homeAddress (street + zip + city + country)
          - mobilePhoneNumber (valid BE format)
          - birthDate
        """
        self.ensure_one()
        if not (self.name and self.email and self.street and self.zip and self.city):
            return False
        if not self.country_id or self.country_id.code != 'BE':
            return False
        if not self.floa_birth_date:
            return False
        # Phone must be a valid BE mobile (+324XXXXXXXX after cleanup)
        raw_phone = self.mobile or self.phone or ''
        phone = re.sub(r'[\s.\-/()]', '', raw_phone)
        if phone.startswith('00'):
            phone = '+' + phone[2:]
        elif phone.startswith('0'):
            phone = '+32' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+32' + phone
        if not re.match(r'^\+324\d{8}$', phone):
            return False
        return True
