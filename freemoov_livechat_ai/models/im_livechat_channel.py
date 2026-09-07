from odoo import Command, models, _
from odoo.addons.bus.websocket import WebsocketConnectionHandler


class ImLivechatChannel(models.Model):
    _inherit = 'im_livechat.channel'

    def _freemoov_ai_available(self):
        params = self.env['ir.config_parameter'].sudo()
        return (params.get_param('freemoov_livechat_ai.enabled') == 'True'
                and params.get_param('freemoov_livechat_ai.dry_run') != 'True'
                and bool(params.get_param('freemoov_livechat_ai.api_key'))
                and bool(self.env.ref('freemoov_livechat_ai.partner_ai_bot', raise_if_not_found=False)))

    def get_livechat_info(self, username=None):
        info = super().get_livechat_info(username=username)
        if self._freemoov_ai_available():
            info['available'] = True
            if not info.get('options'):
                info['options'] = self._get_channel_infos()
                info['options'].update({
                    'websocket_worker_version': WebsocketConnectionHandler._VERSION,
                    'current_partner_id': self.env.user.partner_id.id if not self.env.user._is_public() else None,
                    'default_username': username or _('Visitor'),
                })
        return info

    def _get_livechat_discuss_channel_vals(self, anonymous_name, previous_operator_id=None,
                                         chatbot_script=None, user_id=None, country_id=None, lang=None):
        if not self._freemoov_ai_available() or chatbot_script:
            return super()._get_livechat_discuss_channel_vals(
                anonymous_name, previous_operator_id=previous_operator_id,
                chatbot_script=chatbot_script, user_id=user_id, country_id=country_id, lang=lang)
        bot = self.env.ref('freemoov_livechat_ai.partner_ai_bot')
        members = [Command.create({'partner_id': bot.id, 'is_pinned': False})]
        visitor = self.env['res.users'].browse(user_id).exists() if user_id else self.env['res.users']
        if visitor and visitor.active and visitor.partner_id != bot:
            members.append(Command.create({'partner_id': visitor.partner_id.id}))
        return {
            'name': '%s / %s' % (visitor.display_name or anonymous_name, bot.name),
            'channel_type': 'livechat', 'livechat_active': True,
            'livechat_channel_id': self.id, 'livechat_operator_id': bot.id,
            'channel_member_ids': members, 'chatbot_current_step_id': False,
            'anonymous_name': False if visitor else anonymous_name, 'country_id': country_id,
        }
