# -*- coding: utf-8 -*-
"""
Post-migration 17.0.1.0.1 — restore des 2 mail.template customisés par
l'utilisateur sur prod v16, perdus lors de l'upgrade Odoo SA vers v17.

Templates détectés comme modifiés (write_date != create_date) :
- Template id 1 (xml_id auth_signup.reset_password_email) :
  "Settings: User Reset Password" — customisé le 2025-03-15
- Template id 27 (xml_id repair.mail_template_repair_quotation) :
  "Repair: Quotation" — customisé le 2025-03-15

L'upgrade v17 a supprimé les xml_ids v16 (auth_signup.reset_password_email
n'existe plus — remplacé par auth_signup.set_password_email qui fait le
même job mais avec un body différent). Pour préserver la customisation
utilisateur, on recrée les 2 templates avec leurs external IDs dédiés
website_freemoov.mail_template_reset_password_v16 et
website_freemoov.mail_template_repair_quotation_v16.

Idempotent — si le template existe déjà (via xml_id), update seulement
si le body_html est le défaut (pas déjà restauré).
"""
import logging
import json

_logger = logging.getLogger(__name__)


_TEMPLATES_JSON = r"""
{
  "website_freemoov.mail_template_reset_password_v16": [
    "res.users",
    {
      "name": {
        "en_US": "Settings: User Reset Password",
        "fr_BE": "Paramètres : Réinitialisation du mot de passe de l'utilisateur",
        "fr_FR": "Paramètres : Réinitialisation du mot de passe de l'utilisateur"
      },
      "subject": {
        "en_US": "Password reset",
        "fr_BE": "Réinitialisation du mot de passe",
        "fr_FR": "Réinitialisation du mot de passe"
      },
      "body_html": {
        "en_US": "<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"padding-top: 16px; background-color: #FFFFFF; font-family:Verdana, Arial,sans-serif; color: #454748; width: 100%; border-collapse:separate;\"><tr><td align=\"center\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"padding: 16px; background-color: #FFFFFF; color: #454748; border-collapse:separate;\">\n<tbody>\n    <!-- HEADER -->\n    <tr>\n        <td align=\"center\" style=\"min-width: 590px;\">\n            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"min-width: 590px; background-color: white; padding: 0px 8px 0px 8px; border-collapse:separate;\">\n                <tr><td valign=\"middle\">\n                    <span style=\"font-size: 10px;\">Your Account</span><br/>\n                    <span style=\"font-size: 20px; font-weight: bold;\">\n                        <t t-out=\"object.name or ''\">Marc Demo</t>\n                    </span>\n                </td><td valign=\"middle\" align=\"right\">\n                    <img t-attf-src=\"/logo.png?company={{ object.company_id.id }}\" style=\"padding: 0px; margin: 0px; height: auto; width: 80px;\" t-att-alt=\"object.company_id.name\"/>\n                </td></tr>\n                <tr><td colspan=\"2\" style=\"text-align:center;\">\n                  <hr width=\"100%\" style=\"background-color:rgb(204,204,204);border:medium none;clear:both;display:block;font-size:0px;min-height:1px;line-height:0; margin: 16px 0px 16px 0px;\"/>\n                </td></tr>\n            </table>\n        </td>\n    </tr>\n    <!-- CONTENT -->\n    <tr>\n        <td align=\"center\" style=\"min-width: 590px;\">\n            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"min-width: 590px; background-color: white; padding: 0px 8px 0px 8px; border-collapse:separate;\">\n                <tr><td valign=\"top\" style=\"font-size: 13px;\">\n                    <div>\n                        Dear <t t-out=\"object.name or ''\">Marc Demo</t>,<br/><br/>\n                        A password reset was requested for the Odoo account linked to this email.\n                        You may change your password by following this link which will remain valid during 24 hours:<br/>\n                        <div style=\"margin: 16px 0px 16px 0px;\">\n                            <a t-att-href=\"object.signup_url\" style=\"background-color: #875A7B; padding: 8px 16px 8px 16px; text-decoration: none; color: #fff; border-radius: 5px; font-size:13px;\">\n                                Change password\n                            </a>\n                        </div>\n                        If you do not expect this, you can safely ignore this email.<br/><br/>\n                        Thanks,\n                        <t t-if=\"user.signature\">\n                            <br/>\n                            <t t-out=\"user.signature or ''\">--<br/>Mitchell Admin</t>\n                        </t>\n                    </div>\n                </td></tr>\n                <tr><td style=\"text-align:center;\">\n                  <hr width=\"100%\" style=\"background-color:rgb(204,204,204);border:medium none;clear:both;display:block;font-size:0px;min-height:1px;line-height:0; margin: 16px 0px 16px 0px;\"/>\n                </td></tr>\n            </table>\n        </td>\n    </tr>\n    <!-- FOOTER -->\n    <tr>\n        <td align=\"center\" style=\"min-width: 590px;\">\n            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"min-width: 590px; background-color: white; font-size: 11px; padding: 0px 8px 0px 8px; border-collapse:separate;\">\n                <tr><td valign=\"middle\" align=\"left\">\n                    <t t-out=\"object.company_id.name or ''\">YourCompany</t>\n                </td></tr>\n                <tr><td valign=\"middle\" align=\"left\" style=\"opacity: 0.7;\">\n                    <t t-out=\"object.company_id.phone or ''\">+1 650-123-4567</t>\n\n                    <t t-if=\"object.company_id.email\">\n                        | <a t-att-href=\"'mailto:%s' % object.company_id.email\" style=\"text-decoration:none; color: #454748;\" t-out=\"object.company_id.email or ''\">info@yourcompany.com</a>\n                    </t>\n                    <t t-if=\"object.company_id.website\">\n                        | <a t-att-href=\"'%s' % object.company_id.website\" style=\"text-decoration:none; color: #454748;\" t-out=\"object.company_id.website or ''\">http://www.example.com</a>\n                    </t>\n                </td></tr>\n            </table>\n        </td>\n    </tr>\n</tbody>\n</table>\n</td></tr>\n<!-- POWERED BY -->\n<tr><td align=\"center\" style=\"min-width: 590px;\">\n    <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"min-width: 590px; background-color: #F1F1F1; color: #454748; padding: 8px; border-collapse:separate;\">\n      <tr><td style=\"text-align: center; font-size: 13px;\">\n        Powered by <a target=\"_blank\" href=\"https://www.odoo.com?utm_source=db&amp;utm_medium=auth\" style=\"color: #875A7B;\">Odoo</a>\n      </td></tr>\n    </table>\n</td></tr>\n</table>\n            ",
        "fr_BE": "<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"padding:16px 0 0 0;box-sizing:border-box;caption-side:bottom;padding-top: 16px; background-color: #FFFFFF; font-family:Verdana, Arial,sans-serif; color: #454748; width: 100%; border-collapse:separate;\" width=\"100%\"><tbody style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><td align=\"center\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"box-sizing: border-box; caption-side: bottom; padding: 16px; background-color: #ffffff; color: #454748; border-collapse: separate; font-family: Verdana, Arial, sans-serif;\">\n<tbody style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\">\n    \n    <tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\">\n        <td align=\"center\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px;min-width:590px\">\n            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"box-sizing: border-box; caption-side: bottom; min-width: 590px; background-color: white; padding: 0px 8px; border-collapse: separate; color: #454748; font-family: Verdana, Arial, sans-serif;\">\n                <tbody style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><td valign=\"middle\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\">\n                    <span style=\"font-size: 10px;\">Votre compte</span><br>\n                    <span style=\"font-size: 20px; font-weight: bold;\">\n                        <t t-out=\"object.name or ''\">Marc Demo</t>\n                    </span>\n                </td><td valign=\"middle\" align=\"right\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\">\n                    <img t-attf-src=\"/logo.png?company={{ object.company_id.id }}\" style=\"box-sizing:border-box;vertical-align:middle;padding: 0px; margin: 0px; height: auto; width: 80px;\" t-att-alt=\"object.company_id.name\" width=\"80\">\n                </td></tr>\n                <tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><td colspan=\"2\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px;text-align:center\">\n                  <hr width=\"100%\" style=\"border-style:none;border-left-width:medium;border-bottom-width:medium;border-right-width:medium;border-top-width:medium;box-sizing:border-box;height:1px;opacity:0.25;color:#454748;background-color:#cccccc;border:medium none;clear:both;display:block;font-size:0px;min-height:1px;line-height:0;margin:16px 0px\">\n                </td></tr>\n            </tbody></table>\n        </td>\n    </tr>\n    \n    <tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\">\n        <td align=\"center\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px;min-width:590px\">\n            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"box-sizing: border-box; caption-side: bottom; min-width: 590px; background-color: white; padding: 0px 8px; border-collapse: separate; color: #454748; font-family: Verdana, Arial, sans-serif;\">\n                <tbody style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><td valign=\"top\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px;font-size:13px\">\n                    <div>\n                        Cher/Chère <t t-out=\"object.name or ''\">Marc Demo</t>,<br><br>\n                        Une réinitialisation du mot de passe a été demandée pour le compte Odoo lié à cet email.\n                        Vous pouvez changer votre mot de passe en utilisant ce lien qui restera valide pendant 24 heures :<br>\n                        <div style=\"margin: 16px 0px 16px 0px;\">\n                            <a t-att-href=\"object.signup_url\" style=\"box-sizing:border-box;background-color: #875A7B; padding: 8px 16px 8px 16px; text-decoration: none; color: #fff; border-radius: 5px; font-size:13px;\">\n                                Changer de mot de passe\n                            </a>\n                        </div>\n                        Si vous n'attendiez pas cet email, vous pouvez l'ignorer en toute sécurité.<br><br>\n                        Merci,\n                        <t t-if=\"user.signature\">\n                            <br>\n                            <t t-out=\"user.signature or ''\">--<br>Mitchell Admin</t>\n                        </t><br><img src=\"/web/image/14724-ccaa618a/Freemoov_RGB_Logo%20positif.png\" class=\"img img-fluid o_we_custom_image\" style=\"box-sizing:border-box;display:inline-block;height:auto;max-width:100%;vertical-align:middle;width: 25%; mso-hide: all; mso-hide: all;\" width=\"25%\"><br></div>\n                </td></tr>\n                <tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><td style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px;text-align:center\">\n                  <hr width=\"100%\" style=\"border-style:none;border-left-width:medium;border-bottom-width:medium;border-right-width:medium;border-top-width:medium;box-sizing:border-box;height:1px;opacity:0.25;color:#454748;background-color:#cccccc;border:medium none;clear:both;display:block;font-size:0px;min-height:1px;line-height:0;margin:16px 0px\">\n                </td></tr>\n            </tbody></table>\n        </td>\n    </tr>\n    \n    <tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\">\n        <td align=\"center\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px;min-width:590px\">\n            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"box-sizing: border-box; caption-side: bottom; min-width: 590px; background-color: white; font-size: 11px; padding: 0px 8px; border-collapse: separate; color: #454748; font-family: Verdana, Arial, sans-serif;\">\n                <tbody style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><td valign=\"middle\" align=\"left\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\">\n                    <t t-out=\"object.company_id.name or ''\">YourCompany</t>\n                </td></tr>\n                <tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><td valign=\"middle\" align=\"left\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px;opacity:0.7\">\n                    <t t-out=\"object.company_id.phone or ''\">+1 650-123-4567</t>\n\n                    <t t-if=\"object.company_id.email\">\n                        | <a t-att-href=\"'mailto:%s' % object.company_id.email\" style=\"box-sizing:border-box;text-decoration:none; color: #454748;\" t-out=\"object.company_id.email or ''\">info@yourcompany.com</a>\n                    </t>\n                    <t t-if=\"object.company_id.website\">\n                        | <a t-att-href=\"'%s' % object.company_id.website\" style=\"box-sizing:border-box;text-decoration:none; color: #454748;\" t-out=\"object.company_id.website or ''\">http://www.example.com</a>\n                    </t>\n                </td></tr>\n            </tbody></table>\n        </td>\n    </tr>\n</tbody>\n</table>\n</td></tr>\n\n<tr style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px\"><td align=\"center\" style=\"border-style:none;box-sizing:border-box;border-left-width:0px;border-bottom-width:0px;border-right-width:0px;border-top-width:0px;min-width:590px\"><br></td></tr>\n</tbody></table>\n            ",
        "fr_FR": "<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"padding-top: 16px; background-color: #FFFFFF; font-family:Verdana, Arial,sans-serif; color: #454748; width: 100%; border-collapse:separate;\"><tr><td align=\"center\">\n<table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"padding: 16px; background-color: #FFFFFF; color: #454748; border-collapse:separate;\">\n<tbody>\n    <!-- HEADER -->\n    <tr>\n        <td align=\"center\" style=\"min-width: 590px;\">\n            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"min-width: 590px; background-color: white; padding: 0px 8px 0px 8px; border-collapse:separate;\">\n                <tr><td valign=\"middle\">\n                    <span style=\"font-size: 10px;\">Votre compte</span><br>\n                    <span style=\"font-size: 20px; font-weight: bold;\">\n                        <t t-out=\"object.name or ''\">Marc Demo</t>\n                    </span>\n                </td><td valign=\"middle\" align=\"right\">\n                    <img t-attf-src=\"/logo.png?company={{ object.company_id.id }}\" style=\"padding: 0px; margin: 0px; height: auto; width: 80px;\" t-att-alt=\"object.company_id.name\">\n                </td></tr>\n                <tr><td colspan=\"2\" style=\"text-align:center;\">\n                  <hr width=\"100%\" style=\"background-color:rgb(204,204,204);border:medium none;clear:both;display:block;font-size:0px;min-height:1px;line-height:0; margin: 16px 0px 16px 0px;\">\n                </td></tr>\n            </table>\n        </td>\n    </tr>\n    <!-- CONTENT -->\n    <tr>\n        <td align=\"center\" style=\"min-width: 590px;\">\n            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"min-width: 590px; background-color: white; padding: 0px 8px 0px 8px; border-collapse:separate;\">\n                <tr><td valign=\"top\" style=\"font-size: 13px;\">\n                    <div>\n                        Cher <t t-out=\"object.name or ''\">Marc Demo</t>,<br><br>\n                        Une réinitialisation de mot de passe a été demandée pour le compte Odoo lié à cette adresse e-mail.\n                        Vous pouvez changer votre mot de passe en utilisant ce lien qui restera valide pendant 24 heures :<br>\n                        <div style=\"margin: 16px 0px 16px 0px;\">\n                            <a t-att-href=\"object.signup_url\" style=\"background-color: #875A7B; padding: 8px 16px 8px 16px; text-decoration: none; color: #fff; border-radius: 5px; font-size:13px;\">\n                                Changer de mot de passe\n                            </a>\n                        </div>\n                        Si vous ne vous attendez pas à cet e-mail, vous pouvez l'ignorer en toute sécurité.<br><br>\n                        Merci,\n                        <t t-if=\"user.signature\">\n                            <br>\n                            <t t-out=\"user.signature or ''\">--<br>Mitchell Admin</t>\n                        </t>\n                    </div>\n                </td></tr>\n                <tr><td style=\"text-align:center;\">\n                  <hr width=\"100%\" style=\"background-color:rgb(204,204,204);border:medium none;clear:both;display:block;font-size:0px;min-height:1px;line-height:0; margin: 16px 0px 16px 0px;\">\n                </td></tr>\n            </table>\n        </td>\n    </tr>\n    <!-- FOOTER -->\n    <tr>\n        <td align=\"center\" style=\"min-width: 590px;\">\n            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"min-width: 590px; background-color: white; font-size: 11px; padding: 0px 8px 0px 8px; border-collapse:separate;\">\n                <tr><td valign=\"middle\" align=\"left\">\n                    <t t-out=\"object.company_id.name or ''\">YourCompany</t>\n                </td></tr>\n                <tr><td valign=\"middle\" align=\"left\" style=\"opacity: 0.7;\">\n                    <t t-out=\"object.company_id.phone or ''\">+1 650-123-4567</t>\n\n                    <t t-if=\"object.company_id.email\">\n                        | <a t-att-href=\"'mailto:%s' % object.company_id.email\" style=\"text-decoration:none; color: #454748;\" t-out=\"object.company_id.email or ''\">info@yourcompany.com</a>\n                    </t>\n                    <t t-if=\"object.company_id.website\">\n                        | <a t-att-href=\"'%s' % object.company_id.website\" style=\"text-decoration:none; color: #454748;\" t-out=\"object.company_id.website or ''\">http://www.example.com</a>\n                    </t>\n                </td></tr>\n            </table>\n        </td>\n    </tr>\n</tbody>\n</table>\n</td></tr>\n<!-- POWERED BY -->\n<tr><td align=\"center\" style=\"min-width: 590px;\">\n    <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"590\" style=\"min-width: 590px; background-color: #F1F1F1; color: #454748; padding: 8px; border-collapse:separate;\">\n      <tr><td style=\"text-align: center; font-size: 13px;\">\n        Généré par <a target=\"_blank\" href=\"https://www.odoo.com?utm_source=db&amp;utm_medium=auth\" style=\"color: #875A7B;\">Odoo</a>\n      </td></tr>\n    </table>\n</td></tr>\n</table>\n            "
      },
      "lang": "{{ object.lang }}",
      "email_to": "{{ object.email_formatted }}",
      "reply_to": null,
      "auto_delete": true,
      "description": {
        "en_US": "Sent to user who requested a password reset",
        "fr_BE": "Envoyé à l'utilisateur qui a demandé de réinitialiser son mot de passe",
        "fr_FR": "Envoyé à l'utilisateur qui a demandé de réinitialiser son mot de passe"
      }
    }
  ],
  "website_freemoov.mail_template_repair_quotation_v16": [
    "repair.order",
    {
      "name": {
        "en_US": "Repair: Quotation",
        "fr_BE": "Réparation : Devis",
        "fr_FR": "Réparation : Devis"
      },
      "subject": {
        "en_US": "{{ object.partner_id.name }} Repair Orders (Ref {{ object.name or 'n/a' }})",
        "fr_BE": "{{ object.partner_id.name }} Ordres de réparation (Ref {{ object.name or 'n/a' }})",
        "fr_FR": "{{ object.partner_id.name }} Ordres de réparation (Ref {{ object.name or 'n/a' }})"
      },
      "body_html": {
        "en_US": "<div style=\"margin: 0px; padding: 0px;\">\n    <p style=\"margin: 0px; padding: 0px;font-size: 13px;\">\n        Hello <t t-out=\"object.partner_id.name or ''\">Brandon Freeman</t>,<br>\n        Here is your repair order <strong t-out=\"object.name or ''\">RO/00004</strong>\n        <t t-if=\"object.invoice_method != 'none'\">\n            amounting in <strong><t t-out=\"format_amount(object.amount_total, object.pricelist_id.currency_id) or ''\">$ 100.00</t>.</strong><br>\n        </t>\n        <t t-else=\"\">\n            .<br>\n        </t>\n        You can reply to this email if you have any questions.\n        <br><br>\n        Thank you,\n        <t t-if=\"user.signature\">\n            <br>\n            <t t-out=\"user.signature or ''\">--<br>Mitchell Admin</t>\n        </t>\n    </p>\n</div>",
        "fr_BE": "<div style=\"margin: 0px; padding: 0px;\">\n    <p style=\"box-sizing:border-box;margin: 0px; padding: 0px;font-size: 13px;\">\n        Bonjour <t t-out=\"object.partner_id.name or ''\">Brandon Freeman</t>,<br>\n        Voici votre ordre de réparation <strong t-out=\"object.name or ''\" style=\"box-sizing:border-box;font-weight:bolder;\">RO/00004</strong>\n        <t t-if=\"object.invoice_method != 'none'\">\n            d'un montant de <strong style=\"box-sizing:border-box;font-weight:bolder;\"><t t-out=\"format_amount(object.amount_total, object.pricelist_id.currency_id) or ''\">$ 100.00</t>.</strong><br>\n        </t>\n        <t t-else=\"\">\n            .<br>\n        </t>\n        Vous pouvez répondre à cet email si vous avez des questions.\n        <br><br>\n        Merci,\n        <t t-if=\"user.signature\">\n            <br>\n            <t t-out=\"user.signature or ''\">--<br>Mitchell Admin</t>\n        </t>\n    </p>\n</div>",
        "fr_FR": "<div style=\"margin: 0px; padding: 0px;\">\n    <p style=\"margin: 0px; padding: 0px;font-size: 13px;\">\n        Bonjour <t t-out=\"object.partner_id.name or ''\">Brandon Freeman</t>,<br>\n        Voici votre ordre de réparation <strong t-out=\"object.name or ''\">RO/00004</strong>\n        <t t-if=\"object.invoice_method != 'none'\">\n            d'un montant de <strong><t t-out=\"format_amount(object.amount_total, object.pricelist_id.currency_id) or ''\">$ 100.00</t>.</strong><br>\n        </t>\n        <t t-else=\"\">\n            .<br>\n        </t>\n        N'hésitez pas à répondre à cet e-mail si vous avez des questions.\n        <br><br>\n        Merci,\n        <t t-if=\"user.signature\">\n            <br>\n            <t t-out=\"user.signature or ''\">--<br>Mitchell Admin</t>\n        </t>\n    </p>\n</div>"
      },
      "lang": "{{ object.partner_id.lang }}",
      "email_to": null,
      "reply_to": null,
      "auto_delete": true,
      "description": {
        "en_US": "Sent manually when clicking on \"Send Quotation\" on a repair order",
        "fr_BE": "Envoyé manuellement en cliquant sur \"Envoyer le devis\" dans le cadre d'un ordre de réparation",
        "fr_FR": "Envoyé manuellement en cliquant sur \"Envoyer le devis\" dans le cadre d'un ordre de réparation"
      }
    }
  ]
}
"""
TEMPLATES_DATA = json.loads(_TEMPLATES_JSON)


def _restore_template(env, xml_id, model, data):
    """Upsert le template via son xml_id. Si template existant, skip."""
    ModelData = env['ir.model.data'].sudo()
    Template = env['mail.template'].sudo()

    existing = env.ref(xml_id, raise_if_not_found=False)
    if existing:
        _logger.info(
            "[17.0.1.0.1] Template %s already exists (id=%d), skip.",
            xml_id, existing.id,
        )
        return

    vals = {
        'name': data['name'],
        'subject': data['subject'],
        'body_html': data['body_html'],
        'model_id': env['ir.model']._get_id(model),
        'lang': data.get('lang'),
        'email_to': data.get('email_to'),
        'reply_to': data.get('reply_to'),
        'auto_delete': data.get('auto_delete', False),
        'description': data.get('description'),
    }
    # Filtre None
    vals = {k: v for k, v in vals.items() if v is not None}

    new_tmpl = Template.create(vals)
    module, name = xml_id.split('.', 1)
    ModelData.create({
        'module': module,
        'name': name,
        'model': 'mail.template',
        'res_id': new_tmpl.id,
        'noupdate': True,
    })
    _logger.info(
        "[17.0.1.0.1] Created template %s (id=%d) — %r",
        xml_id, new_tmpl.id,
        data['name'].get('en_US') if isinstance(data['name'], dict) else data['name'],
    )


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    for xml_id, (model, data) in TEMPLATES_DATA.items():
        try:
            _restore_template(env, xml_id, model, data)
        except Exception as e:
            _logger.warning(
                "[17.0.1.0.1] Failed to restore %s: %s", xml_id, e,
            )

    env.registry.clear_cache()
    _logger.info("[17.0.1.0.1] Post-migrate complete — cache cleared")
