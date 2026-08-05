"""Inspect the actual prompt + messages that would be sent to Anthropic."""
from odoo.addons.freemoov_livechat_ai.services.prompt_builder import (
    build_system_prompt, build_messages_from_channel
)

Channel = env["discuss.channel"].sudo()
LCC = env["im_livechat.channel"].sudo()
lcc = LCC.search([], limit=1)
operator = lcc.user_ids[0].partner_id if lcc and lcc.user_ids else env.ref("base.partner_admin")

chan = Channel.create({
    "name": "TEST AI INSPECT",
    "channel_type": "livechat",
    "livechat_operator_id": operator.id,
    "livechat_channel_id": lcc.id if lcc else False,
})

# Simulate visitor history
env["mail.message"].sudo().create({
    "model": "discuss.channel", "res_id": chan.id,
    "body": "<p>Bonjour</p>", "message_type": "comment",
    "subtype_id": env.ref("mail.mt_comment").id, "author_id": False,
})
env["mail.message"].sudo().create({
    "model": "discuss.channel", "res_id": chan.id,
    "body": "<p>Est-ce que je peux payer en plusieurs fois avec le CPAS ?</p>",
    "message_type": "comment",
    "subtype_id": env.ref("mail.mt_comment").id, "author_id": False,
})
env.cr.commit()

prompt = build_system_prompt(env)
msgs = build_messages_from_channel(chan)

print("=== SYSTEM PROMPT LENGTH:", len(prompt))
print("=== SYSTEM PROMPT (preview first 2000 chars) ===")
print(prompt[:2000])
print("=== END PREVIEW ===")
print()
print("=== CATALOG SECTION (last 2000 chars) ===")
print(prompt[-2000:])
print()
print("=== MESSAGES ===")
import json
print(json.dumps(msgs, ensure_ascii=False, indent=2))
