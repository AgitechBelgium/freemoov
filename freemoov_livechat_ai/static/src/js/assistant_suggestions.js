/** @odoo-module **/

import { Thread } from "@mail/core/common/thread";

import { patch } from "@web/core/utils/patch";
import { isFreemoovThread } from "./assistant_presentation";

/**
 * The three public openings offered before the visitor has typed anything.
 *
 * Not translated on purpose: the shop is Belgian and French-speaking, the
 * system prompt is written in French, and a suggestion is not a label but the
 * literal text posted to the channel — a translated button would send the
 * assistant a sentence its prompt never anticipated.
 *
 * Repair tracking is intentionally not advertised while its business rollout
 * remains disabled. Human contact is a separate persistent action.
 */
export const ASSISTANT_SUGGESTIONS = [
    "Trouver une trottinette",
    "Suivre ma commande",
    "Horaires et magasins",
];

patch(Thread.prototype, {
    get isFreemoovAssistant() {
        return isFreemoovThread(this.env, this.props.thread);
    },
    get assistantSuggestions() {
        return ASSISTANT_SUGGESTIONS;
    },
    get canRequestFreemoovAdviser() {
        return this.isFreemoovAssistant && this.props.thread.operator?.id ===
            this.env.services["im_livechat.livechat"].options.freemoov_ai_bot_partner_id;
    },

    get showAssistantSuggestions() {
        const thread = this.props.thread;
        if (!this.isFreemoovAssistant) {
            return false;
        }
        // An Odoo chatbot script drives its own conversation, with its own
        // answer buttons under each step. Two sets of buttons proposing two
        // different things is how a visitor ends up answering neither.
        if (this.chatbotService?.active) {
            return false;
        }
        if (this.assistantTyping?.isWaitingFor(thread)) {
            return false;
        }
        // Openings, so: only until the visitor has said something. The operator's
        // welcome message does not count — it is what the suggestions answer.
        return !thread.messages.some((message) => message.isSelfAuthored);
    },

    /**
     * @param {string} text
     */
    sendAssistantSuggestion(text) {
        return this.threadService.post(this.props.thread, text);
    },
});
