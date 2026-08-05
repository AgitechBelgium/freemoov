"""Ce que l'écran Réglages montre, et ce qu'il enregistre vraiment.

Deux pièges tiennent tout ce fichier :

* un paramètre lu par le code mais absent de l'écran est un réglage que
  personne ne touche ; un champ affiché qui n'écrit rien que le code lise est
  une promesse que le logiciel ne tient pas (`delay_seconds` a vécu ainsi
  pendant dix tâches) ;
* le framework lit un paramètre booléen avec `bool(value)` et l'efface quand
  la case est décochée, alors que ce module le lit avec `value == "True"` et
  traite l'absence de `dry_run` comme « mode observation ». Sans les
  surcharges de `get_values` / `set_values`, les cases mentent dans les deux
  sens.
"""
from odoo.tests import tagged

from ..services.tools import DRY_RUN_PARAM
from .common import FreemoovAiCase

PREFIX = "freemoov_livechat_ai."
SETTINGS_VIEW = "freemoov_livechat_ai.view_res_config_settings_livechat_ai"


@tagged("post_install", "-at_install", "freemoov_ai")
class TestSettings(FreemoovAiCase):
    def _settings(self, **values):
        return self.env["res.config.settings"].create(values)

    def _shipped_params(self):
        """Les paramètres livrés par le module, lus dans la base plutôt que
        dans le fichier qui les déclare."""
        data = self.env["ir.model.data"].search([
            ("module", "=", "freemoov_livechat_ai"),
            ("model", "=", "ir.config_parameter"),
        ])
        return set(self.env["ir.config_parameter"].sudo()
                   .browse(data.mapped("res_id")).exists().mapped("key"))

    def _field_params(self):
        return {
            field.config_parameter
            for field in self.env["res.config.settings"]._fields.values()
            if getattr(field, "config_parameter", None)
            and field.config_parameter.startswith(PREFIX)
        }

    # -- couverture -------------------------------------------------------
    def test_every_shipped_parameter_is_reachable_from_the_backend(self):
        unreachable = self._shipped_params() - self._field_params() - {DRY_RUN_PARAM}
        self.assertFalse(unreachable, "absents de l'écran Réglages : %s" % unreachable)
        # `dry_run` n'a pas de `config_parameter` (voir le module), mais il a
        # bien un champ : c'est le seul écart admis ci-dessus.
        self.assertIn("freemoov_ai_dry_run", self.env["res.config.settings"]._fields)

    def test_no_field_writes_a_parameter_nobody_reads(self):
        """Le symétrique : une faute de frappe dans `config_parameter` donne
        un champ qui s'enregistre sans effet, exactement comme un réglage mort.
        `api_key` est la seule exception voulue — un secret n'a pas de valeur
        par défaut à livrer dans un fichier de données.
        """
        self.assertEqual(self._field_params() - self._shipped_params(),
                         {PREFIX + "api_key"})

    def test_every_field_appears_in_the_settings_view(self):
        arch = self.env.ref(SETTINGS_VIEW).arch
        for name in self.env["res.config.settings"]._fields:
            if name.startswith("freemoov_ai_"):
                self.assertIn('name="%s"' % name, arch)

    def test_the_dead_delay_setting_is_gone(self):
        """Réglé, enregistré, affiché — et lu par personne : la boucle agent
        n'a jamais attendu quoi que ce soit."""
        self.assertNotIn("freemoov_ai_delay_seconds",
                         self.env["res.config.settings"]._fields)
        self.assertNotIn(PREFIX + "delay_seconds", self._shipped_params())

    # -- les interrupteurs disent la vérité -------------------------------
    def test_a_switch_shipped_off_is_displayed_off(self):
        """`bool("False")` vaut True : lues par le framework, les cases
        s'affichaient cochées sur une base où tout était désactivé."""
        ICP = self.env["ir.config_parameter"].sudo()
        for key in ("enabled", "verification_test_mode", "repair_tool_enabled"):
            ICP.set_param(PREFIX + key, "False")
        settings = self._settings()
        self.assertFalse(settings.freemoov_ai_enabled)
        self.assertFalse(settings.freemoov_ai_verification_test_mode)
        self.assertFalse(settings.freemoov_ai_repair_tool_enabled)

    def test_ticking_a_switch_is_what_the_code_reads(self):
        settings = self._settings(freemoov_ai_enabled=True,
                                  freemoov_ai_verification_test_mode=True)
        settings.set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        self.assertEqual(ICP.get_param(PREFIX + "enabled"), "True")
        self.assertTrue(self.channel._freemoov_ai_is_enabled())
        self.assertEqual(ICP.get_param(PREFIX + "verification_test_mode"), "True")
        self.assertTrue(self._settings().freemoov_ai_enabled)

    def test_unticking_a_switch_turns_it_off_for_good(self):
        self._settings(freemoov_ai_enabled=True).set_values()
        self._settings(freemoov_ai_enabled=False).set_values()
        self.assertFalse(self.channel._freemoov_ai_is_enabled())
        self.assertFalse(self._settings().freemoov_ai_enabled)

    # -- dry run ----------------------------------------------------------
    def test_dry_run_can_actually_be_switched_off(self):
        """`set_param` efface la ligne pour une valeur fausse, et un `dry_run`
        absent vaut « mode observation » : câblée comme les autres, la case
        pouvait être décochée, enregistrée, et ne rien changer du tout.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(DRY_RUN_PARAM, "True")
        self.assertTrue(self.channel._freemoov_ai_is_dry_run(), "précondition")

        self._settings(freemoov_ai_dry_run=False).set_values()

        self.assertEqual(ICP.get_param(DRY_RUN_PARAM), "False")
        self.assertFalse(self.channel._freemoov_ai_is_dry_run())
        self.assertFalse(self._settings().freemoov_ai_dry_run)

    def test_dry_run_can_be_switched_back_on(self):
        self._settings(freemoov_ai_dry_run=False).set_values()
        self._settings(freemoov_ai_dry_run=True).set_values()
        self.assertTrue(self.channel._freemoov_ai_is_dry_run())
        self.assertTrue(self._settings().freemoov_ai_dry_run)

    def test_dry_run_is_on_when_nobody_has_decided(self):
        self.env["ir.config_parameter"].sudo().search(
            [("key", "=", DRY_RUN_PARAM)]).unlink()
        self.assertTrue(self.channel._freemoov_ai_is_dry_run())
        self.assertTrue(self._settings().freemoov_ai_dry_run)

    # -- entiers ----------------------------------------------------------
    def test_the_token_ceiling_can_be_lifted_from_the_backend(self):
        """0 n'est pas enregistrable — le framework efface le paramètre pour
        un entier faux et le défaut revient. -1 est ce que propose l'aide du
        champ, et c'est ce que la boucle honore."""
        self._settings(freemoov_ai_conversation_token_budget=-1).set_values()
        self.assertEqual(
            self.channel._freemoov_ai_config()["conversation_token_budget"], -1)

    # -- entretien --------------------------------------------------------
    def test_both_purges_are_scheduled(self):
        """Two crons rather than one: each runs on the model it empties, and
        an administrator has to be able to stop one without the other."""
        for xmlid, code in (
            ("freemoov_livechat_ai.ir_cron_gc_verifications", "_gc_verifications"),
            ("freemoov_livechat_ai.ir_cron_gc_api_logs", "_gc_api_logs"),
        ):
            cron = self.env.ref(xmlid)
            self.assertTrue(cron.active, xmlid)
            self.assertEqual((cron.interval_number, cron.interval_type), (1, "days"))
            self.assertIn(code, cron.code)
            # A cron pointing at another model would run `model._gc_...` on it.
            self.assertTrue(hasattr(self.env[cron.model_id.model], code))

    def test_the_integers_land_where_the_turn_reads_them(self):
        self._settings(
            freemoov_ai_max_tokens=512,
            freemoov_ai_client_timeout=9,
            freemoov_ai_rate_limit_per_min=7,
        ).set_values()
        cfg = self.channel._freemoov_ai_config()
        self.assertEqual(
            (cfg["max_tokens"], cfg["client_timeout"], cfg["rate_limit_per_min"]),
            (512, 9, 7))
