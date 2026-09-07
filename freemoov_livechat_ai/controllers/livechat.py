from odoo import http
from odoo.http import request
from odoo.addons.im_livechat.controllers.main import LivechatController


class FreemoovLivechatController(LivechatController):
    @http.route()
    def livechat_init(self, channel_id):
        result = super().livechat_init(channel_id)
        channel = request.env['im_livechat.channel'].sudo().browse(channel_id).exists()
        if channel and channel._freemoov_ai_available():
            # Keep explicit hide rules and native chatbot routing intact.
            result['available_for_me'] = (result.get('rule') or {}).get('action') != 'hide_button'
        return result
