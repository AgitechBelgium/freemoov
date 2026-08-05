/** @odoo-module **/

import { Thread } from "@mail/core/common/thread";

import { patch } from "@web/core/utils/patch";

/**
 * The five openings offered before the visitor has typed anything.
 *
 * Not translated on purpose: the shop is Belgian and French-speaking, the
 * system prompt is written in French, and a suggestion is not a label but the
 * literal text posted to the channel — a translated button would send the
 * assistant a sentence its prompt never anticipated.
 *
 * The last one is the way out. It posts the exact sentence the system prompt
 * (Task 7) recognises as a request for a human, which makes the model answer
 * with `[ESCALATE]`; the agent loop then flags the turn and the conversation
 * goes to an operator. It is that literal sentence that carries the behaviour,
 * so it may not be reworded here alone.
 */
export const ASSISTANT_SUGGESTIONS = [
    "Trouver une trottinette",
    "Suivre ma commande",
    "Suivre ma réparation",
    "Horaires et magasins",
    "Je veux parler à un conseiller",
];

patch(Thread.prototype, {
    get assistantSuggestions() {
        return ASSISTANT_SUGGESTIONS;
    },

    get showAssistantSuggestions() {
        const thread = this.props.thread;
        if (thread?.type !== "livechat") {
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
