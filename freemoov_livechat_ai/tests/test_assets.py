from odoo.modules.module import get_manifest
from odoo.tests import tagged

from .common import FreemoovAiCase

# The bundle the widget assets are declared in — checked against
# `im_livechat/__manifest__.py`, not taken on trust.
DECLARED_BUNDLE = "im_livechat.assets_embed_core"

# ...and the bundles that bundle actually reaches the browser through. It is
# never served on its own: it opens with
# `('remove', 'web/static/src/core/browser/title_service.js')`, a file it does
# not contain, so resolving it standalone raises outright. It only makes sense
# inside a bundle that has already pulled in the web core — which is exactly the
# pair below: the widget served on freemoov.com comes from `web.assets_frontend`,
# the one embedded on a third-party page from `assets_embed_external` (and from
# `assets_embed_cors`, which is that same bundle plus the CORS glue).
SERVED_BUNDLES = ("web.assets_frontend", "im_livechat.assets_embed_external")

MODULE_PREFIX = "/freemoov_livechat_ai/"

DECLARED_PATHS = [
    "/freemoov_livechat_ai/static/src/js/assistant_avatar.js",
    "/freemoov_livechat_ai/static/src/js/assistant_suggestions.js",
    "/freemoov_livechat_ai/static/src/js/assistant_typing.js",
    "/freemoov_livechat_ai/static/src/scss/assistant_theme.scss",
    "/freemoov_livechat_ai/static/src/xml/assistant_thread.xml",
]

# Ours must load after this one. `im_livechat` patches the very same OWL
# component we do (`Thread`, in `embed/common/thread_patch.js`) and `patch()`
# composes in load order: loaded first, our `setup()` would be the one their
# `super()` resolves to, and `chatbotService` — which our own code reads — would
# not exist yet.
IM_LIVECHAT_THREAD_PATCH = "/im_livechat/static/src/embed/common/thread_patch.js"


@tagged("post_install", "-at_install", "freemoov_ai")
class TestAssets(FreemoovAiCase):
    def _bundle_paths(self, bundle):
        """Paths of `bundle`, in load order.

        Read through `_get_asset_paths` rather than by searching `ir.asset`:
        assets declared in a manifest never become `ir.asset` rows (see
        `_fill_asset_paths` step 2, which reads the manifest cache directly), so
        a search would come back empty however well the module is installed.
        Each entry is `(path, full_path, bundle, last_modified)`, and a path only
        makes that list if the file exists on disk — the glob in `_get_paths` is
        what drops the ones that do not.
        """
        IrAsset = self.env["ir.asset"]
        params = IrAsset._get_asset_params()
        return [asset[0] for asset in IrAsset._get_asset_paths(bundle, params)]

    def test_module_is_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "freemoov_livechat_ai")])
        self.assertEqual(module.state, "installed")

    def test_assets_declared_in_widget_bundle(self):
        assets = get_manifest("freemoov_livechat_ai")["assets"]
        self.assertEqual(sorted(assets.keys()), [DECLARED_BUNDLE])
        self.assertEqual(
            sorted("/%s" % path for path in assets[DECLARED_BUNDLE]), DECLARED_PATHS)

    def test_assets_reach_every_flavour_of_the_widget(self):
        for bundle in SERVED_BUNDLES:
            with self.subTest(bundle=bundle):
                paths = self._bundle_paths(bundle)
                ours = sorted(path for path in paths if path.startswith(MODULE_PREFIX))
                self.assertEqual(
                    ours, DECLARED_PATHS,
                    "widget assets missing from %s (a path that resolves to no "
                    "file on disk is dropped silently)" % bundle)

    def test_assets_load_after_im_livechat_patches(self):
        for bundle in SERVED_BUNDLES:
            with self.subTest(bundle=bundle):
                paths = self._bundle_paths(bundle)
                self.assertIn(IM_LIVECHAT_THREAD_PATCH, paths)
                native = paths.index(IM_LIVECHAT_THREAD_PATCH)
                for path in paths:
                    if path.startswith(MODULE_PREFIX) and path.endswith(".js"):
                        self.assertGreater(
                            paths.index(path), native,
                            "%s loads before im_livechat's own Thread patch" % path)

    def test_owl_template_grafts_onto_mail_thread(self):
        """The `t-inherit` xpath still finds the node it aims at.

        `AssetsBundle.js` inlines the bundle's templates, and building them runs
        `apply_inheritance_specs` — which raises when an xpath matches nothing.
        So compiling the bundle is a real check on the graft: the day an Odoo
        release renames `.o-mail-Thread`, this fails here rather than silently
        dropping the suggestions and the typing bubble from the widget.
        """
        bundle = self.env["ir.qweb"]._get_asset_bundle(
            "im_livechat.assets_embed_external", css=False, js=True)
        js = bundle.js().raw.decode()
        self.assertIn("fm-assistant-suggestions", js)
        self.assertIn("showAssistantTyping", js)

    def test_scss_compiles(self):
        """The theme is real CSS by the end of the pipeline.

        Worth a test of its own because a SCSS error does not raise:
        `AssetsBundle.css` collects it in `css_errors` and serves the *previous*
        stylesheet under a banner. Without this, a theme that stopped compiling
        would reach production looking merely unstyled, and nothing in the logs
        of a passing test run would say why.

        Compiled through `assets_embed_external` rather than the declared
        bundle: `assets_embed_core` cannot be resolved on its own (see
        `SERVED_BUNDLES`), and this is the smaller of the two that can.
        """
        bundle = self.env["ir.qweb"]._get_asset_bundle(
            "im_livechat.assets_embed_external", css=True, js=False)
        css = bundle.css().raw.decode()
        self.assertFalse(
            [error for error in bundle.css_errors if MODULE_PREFIX[1:] in error],
            "the theme did not compile: %s" % bundle.css_errors)
        self.assertIn("fm-assistant-suggestion", css)
        self.assertIn("fm-assistant-card", css)
        self.assertIn("o-livechat-LivechatButton", css)
