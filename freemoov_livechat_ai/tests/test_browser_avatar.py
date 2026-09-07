"""Exercise the actual browser modules, not only Python/asset compilation."""
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install', 'freemoov_ai')
class TestBrowserAvatar(HttpCase):
    def test_missing_message_author_uses_default_avatar(self):
        params = self.env['ir.config_parameter'].sudo()
        # Keep the external embed on the test HTTP server, not the copied
        # production/staging base URL (whose channel cannot see our test data).
        params.set_param('web.base.url', self.base_url())
        params.set_param('freemoov_livechat_ai.enabled', 'True')
        params.set_param('freemoov_livechat_ai.dry_run', 'False')
        # The test renders only; no provider request or visitor message.
        params.set_param('freemoov_livechat_ai.api_key', 'unused-browser-test')
        channel = self.env['im_livechat.channel'].create({'name': 'Avatar regression'})
        code = """
            Promise.resolve().then(() => {
                const modules = odoo.loader.modules;
                const { ThreadService } = modules.get('@mail/core/common/thread_service');
                const { Message } = modules.get('@mail/core/common/message');
                const { DEFAULT_AVATAR } = modules.get('@mail/core/common/persona_service');
                if (!modules.has('@freemoov_livechat_ai/js/assistant_typing')) {
                    throw new Error('Assistant extension not loaded');
                }
                const service = Object.create(ThreadService.prototype);
                service.store = {};
                const operator = {id: 123, type: 'partner', eq(other) { return this === other; }};
                const thread = {id: 456, type: 'livechat', model: 'discuss.channel', operator};
                const component = Object.create(Message.prototype);
                component.threadService = service;
                for (const author of [undefined, null]) {
                    component.props = {message: {type: 'comment', author, originThread: thread}};
                    if (component.authorAvatarUrl !== DEFAULT_AVATAR) {
                        throw new Error('Authorless message must use the neutral avatar');
                    }
                }
                if (!service.avatarUrl(operator, thread).endsWith('/im_livechat/operator/123/avatar')) {
                    throw new Error('Operator avatar routing changed');
                }
                const guest = {id: 789, type: 'guest', eq() { return false; }};
                if (!service.avatarUrl(guest, thread).includes('/discuss/channel/456/guest/789/avatar_128')) {
                    throw new Error('Guest avatar routing changed');
                }
                console.log('test successful');
            }).catch(error => console.error(error));
        """
        self.browser_js('/im_livechat/support/%s' % channel.id, code=code,
                        ready="Boolean(window.odoo?.loader?.modules.has('@freemoov_livechat_ai/js/assistant_typing'))",
                        timeout=60)
