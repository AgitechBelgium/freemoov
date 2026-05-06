import logging
import re

from odoo import models

try:
    import phonenumbers
    from phonenumbers import NumberParseException, PhoneNumberFormat
except ImportError:
    phonenumbers = None

_logger = logging.getLogger(__name__)

DOUBLE_PREFIX_REPEATED = re.compile(r"^\+(\d{1,3})\+\1")
DOUBLE_PREFIX_DIFFERENT = re.compile(r"^\+\d{1,3}\+\d")
ZIP_BE = re.compile(r"^[1-9]\d{3}$")
ZIP_FR = re.compile(r"^\d{5}$")
LANG_COUNTRY = re.compile(r"_([A-Z]{2})$")
LANG_COUNTRY_WHITELIST = {"BE", "FR", "NL", "LU", "DE", "ES", "IT", "GB", "IE", "PT", "AT", "CH"}
VAT_PREFIX = re.compile(r"^([A-Z]{2})")

DEFAULT_FALLBACK_COUNTRY = "BE"


class PhoneNormalizer(models.AbstractModel):
    """Pure logic for phone normalization. Stateless, no side effects.

    Used by res.partner (write/create hooks) and the curative wizard.
    """

    _name = "freemoov.phone.normalizer"
    _description = "Phone normalization helper"

    @staticmethod
    def _repair_double_prefix(number):
        """Fix `+32+32...` -> `+32...`. Different prefixes are left alone (caller marks invalid)."""
        if not number:
            return number, False
        m = DOUBLE_PREFIX_REPEATED.match(number)
        if m:
            return "+" + m.group(1) + number[len(m.group(0)):], True
        return number, False

    @staticmethod
    def _strip_double_prefix_different(number):
        return bool(number and DOUBLE_PREFIX_DIFFERENT.match(number) and not DOUBLE_PREFIX_REPEATED.match(number))

    @staticmethod
    def _infer_country_from_partner(partner_vals, fallback=DEFAULT_FALLBACK_COUNTRY):
        """Cascade pays sur un dict-like (vals partner OR record).

        Ordre :
          1. country_code (déjà résolu sur le record en amont, ou code pays explicite)
          2. vat préfixe ISO
          3. lang suffixe _XX
          4. zip pattern (BE 4 digits, FR 5 digits)
          5. fallback BE (avec flag inferred=True)

        Returns (country_code, inferred_bool).
        """
        country_code = partner_vals.get("country_code")
        if country_code:
            return country_code, False

        vat = partner_vals.get("vat") or ""
        if vat:
            m = VAT_PREFIX.match(vat.strip().upper())
            if m:
                return m.group(1), False

        lang = partner_vals.get("lang") or ""
        m = LANG_COUNTRY.search(lang)
        if m and m.group(1) in LANG_COUNTRY_WHITELIST:
            return m.group(1), False

        zip_code = (partner_vals.get("zip") or "").strip()
        if zip_code:
            if ZIP_BE.match(zip_code):
                return "BE", False
            if ZIP_FR.match(zip_code):
                return "FR", False

        return fallback, True

    @classmethod
    def normalize(cls, raw, partner_vals, fallback=DEFAULT_FALLBACK_COUNTRY):
        """Normalize a phone number for a given partner context.

        Returns dict:
            {
                'value': str | None,        # final stored value (E.164 if valid, else raw)
                'valid': bool,
                'country': str | None,      # ISO country resolved
                'country_inferred': bool,   # True if country came from fallback
                'reason': str | None,       # populated when invalid
            }
        """
        if not raw or not raw.strip():
            return {"value": False, "valid": True, "country": None, "country_inferred": False, "reason": None}

        if phonenumbers is None:
            _logger.warning("phonenumbers not installed; skipping normalization for %r", raw)
            return {"value": raw, "valid": True, "country": None, "country_inferred": False, "reason": None}

        cleaned = raw.strip()

        if cls._strip_double_prefix_different(cleaned):
            return {
                "value": cleaned,
                "valid": False,
                "country": None,
                "country_inferred": False,
                "reason": "double_prefix_mismatch",
            }
        cleaned, repaired = cls._repair_double_prefix(cleaned)

        if cleaned.startswith("00") and not cleaned.startswith("000"):
            candidate = "+" + cleaned[2:]
            try:
                parsed = phonenumbers.parse(candidate, None)
                if phonenumbers.is_valid_number(parsed):
                    return {
                        "value": phonenumbers.format_number(parsed, PhoneNumberFormat.E164),
                        "valid": True,
                        "country": phonenumbers.region_code_for_number(parsed),
                        "country_inferred": False,
                        "reason": None,
                    }
            except NumberParseException:
                pass

        if cleaned.startswith("+"):
            try:
                parsed = phonenumbers.parse(cleaned, None)
                if phonenumbers.is_valid_number(parsed):
                    return {
                        "value": phonenumbers.format_number(parsed, PhoneNumberFormat.E164),
                        "valid": True,
                        "country": phonenumbers.region_code_for_number(parsed),
                        "country_inferred": False,
                        "reason": None,
                    }
                return {
                    "value": cleaned,
                    "valid": False,
                    "country": None,
                    "country_inferred": False,
                    "reason": "invalid_international_format",
                }
            except NumberParseException:
                return {
                    "value": cleaned,
                    "valid": False,
                    "country": None,
                    "country_inferred": False,
                    "reason": "parse_error_international",
                }

        country, inferred = cls._infer_country_from_partner(partner_vals, fallback=fallback)
        try:
            parsed = phonenumbers.parse(cleaned, country)
        except NumberParseException:
            return {
                "value": cleaned,
                "valid": False,
                "country": country,
                "country_inferred": inferred,
                "reason": "parse_error_national",
            }
        if not phonenumbers.is_valid_number(parsed):
            return {
                "value": cleaned,
                "valid": False,
                "country": country,
                "country_inferred": inferred,
                "reason": "invalid_national_number",
            }
        return {
            "value": phonenumbers.format_number(parsed, PhoneNumberFormat.E164),
            "valid": True,
            "country": country,
            "country_inferred": inferred,
            "reason": None,
        }
