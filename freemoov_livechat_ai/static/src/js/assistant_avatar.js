/** @odoo-module **/

import { DEFAULT_AVATAR } from "@mail/core/common/persona_service";
import { ThreadService } from "@mail/core/common/thread_service";
import { patch } from "@web/core/utils/patch";

patch(ThreadService.prototype, {
    avatarUrl(persona, thread) {
        // im_livechat dereferences persona.eq() before the base mail service
        // can handle a missing author. A transient/authorless message must
        // not destroy the whole OWL application. Keep a neutral avatar; never
        // guess that the message was written by the bot or another visitor.
        if (!persona) {
            return DEFAULT_AVATAR;
        }
        return super.avatarUrl(...arguments);
    },
});
