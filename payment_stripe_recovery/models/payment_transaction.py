# -*- coding: utf-8 -*-

import logging
from datetime import timedelta, timezone

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Fenêtre de rattrapage : une tx plus jeune que MIN_AGE est encore dans le flux
# nominal (webhook/redirect) ; plus vieille que MAX_AGE, le PaymentIntent est
# expiré côté Stripe et la session client n'existe plus.
RECOVERY_MIN_TX_AGE = timedelta(minutes=5)
RECOVERY_MAX_TX_AGE = timedelta(days=7)
# Une tentative abandonnée (requires_payment_method) n'est classée en erreur
# qu'après ce délai, pour ne pas fermer une tx que le client est en train de payer.
ABANDONED_TX_MIN_AGE = timedelta(hours=1)

# Statuts d'intent qui justifient un traitement immédiat par le rattrapage.
ACTIONABLE_INTENT_STATUSES = ('succeeded', 'requires_capture', 'processing', 'canceled')


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    @api.model_create_multi
    def create(self, vals_list):
        txs = super().create(vals_list)
        txs._check_linked_orders_not_already_paid()
        return txs

    def _check_linked_orders_not_already_paid(self):
        """Bloque la création d'une nouvelle transaction de paiement sur une
        commande dont le montant est déjà couvert par des transactions
        capturées (done/authorized).

        Sans ce verrou, une commande restée en devis après un paiement capturé
        mais non notifié (webhook manqué) reste payable et le client peut être
        prélevé plusieurs fois.
        """
        for tx in self:
            if tx.operation not in ('online_direct', 'online_redirect', 'online_token'):
                continue
            for order in tx.sale_order_ids:
                if order.currency_id.compare_amounts(order.amount_total, 0) <= 0:
                    continue
                captured_txs = order.transaction_ids.filtered(
                    lambda t: t.id != tx.id
                    and t.state in ('done', 'authorized')
                    and t.operation != 'refund'
                )
                captured_amount = sum(captured_txs.mapped('amount'))
                if order.currency_id.compare_amounts(captured_amount, order.amount_total) >= 0:
                    raise ValidationError(_(
                        "A payment has already been captured for order %(order)s "
                        "(transaction %(tx_ref)s). Please do not pay again; if you were "
                        "charged more than once, contact us for a refund.",
                        order=order.name,
                        tx_ref=captured_txs[:1].reference,
                    ))

    @api.model
    def _cron_stripe_recover_transactions(self):
        """Filet de sécurité : réconcilie les transactions Stripe restées en
        draft/pending alors que Stripe connaît l'issue du PaymentIntent.

        Couvre les cas où ni le webhook ni la redirection navigateur n'ont
        atteint Odoo (express checkout Apple Pay/Google Pay, paiement Bancontact
        finalisé dans l'app bancaire sans retour navigateur, webhook en panne).
        """
        now = fields.Datetime.now()
        stuck_txs = self.search([
            ('provider_code', '=', 'stripe'),
            ('state', 'in', ('draft', 'pending')),
            ('operation', 'in', ('online_direct', 'online_redirect', 'online_token', 'offline')),
            ('create_date', '<=', now - RECOVERY_MIN_TX_AGE),
            ('create_date', '>=', now - RECOVERY_MAX_TX_AGE),
        ])
        if not stuck_txs:
            return

        recovered_done = self.browse()
        for provider in stuck_txs.provider_id:
            provider_txs = stuck_txs.filtered(lambda t: t.provider_id == provider)
            try:
                intents_by_reference = self._stripe_fetch_intents_by_reference(
                    provider, min(provider_txs.mapped('create_date'))
                )
            except Exception:
                _logger.exception(
                    "Stripe recovery: unable to fetch payment intents for provider %s (id %s).",
                    provider.name, provider.id,
                )
                continue

            for tx in provider_txs:
                intent = intents_by_reference.get(tx.reference)
                if not intent:
                    continue
                status = intent.get('status')
                if status not in ACTIONABLE_INTENT_STATUSES:
                    # Ne classer une tentative abandonnée en erreur qu'après un délai
                    # de grâce ; les autres statuts intermédiaires restent intouchés.
                    is_stale_abandon = (
                        status == 'requires_payment_method'
                        and tx.create_date <= now - ABANDONED_TX_MIN_AGE
                    )
                    if not is_stale_abandon:
                        continue
                if status == 'succeeded':
                    # Niveau error à dessein : un paiement capturé au PSP sans
                    # confirmation locale doit remonter dans Sentry.
                    _logger.error(
                        "Stripe recovery: payment intent %s for transaction %s was captured "
                        "at Stripe but never confirmed in Odoo; recovering it now.",
                        intent.get('id'), tx.reference,
                    )
                try:
                    with self.env.cr.savepoint():
                        # Réplique de StripeController._include_payment_intent_in_notification_data.
                        notification_data = {
                            'reference': tx.reference,
                            'payment_intent': intent,
                            'payment_method': intent.get('payment_method'),
                        }
                        tx._handle_notification_data('stripe', notification_data)
                except Exception:
                    _logger.exception(
                        "Stripe recovery: failed to process intent %s for transaction %s.",
                        intent.get('id'), tx.reference,
                    )
                    continue
                if tx.state == 'done':
                    recovered_done |= tx

        if recovered_done:
            _logger.info(
                "Stripe recovery: recovered transactions %s.",
                ', '.join(recovered_done.mapped('reference')),
            )
            # Confirme les commandes sans attendre le prochain passage du cron
            # de post-processing.
            self.env.ref('payment.cron_post_process_payment_tx')._trigger()

    @api.model
    def _stripe_fetch_intents_by_reference(self, provider, since_dt):
        """Liste les PaymentIntents Stripe créés depuis ``since_dt`` et les
        indexe par référence de transaction (champ ``description``, renseigné
        par Odoo à la création de l'intent).

        Quand plusieurs intents portent la même référence (le client a relancé
        le paiement sur la même transaction), l'intent capturé est prioritaire.
        """
        created_gte = int(
            (since_dt - timedelta(hours=1)).replace(tzinfo=timezone.utc).timestamp()
        )
        intents_by_reference = {}
        payload = {
            'limit': 100,
            'created[gte]': created_gte,
            'expand[]': 'data.payment_method',
        }
        while True:
            result = provider._stripe_make_request(
                'payment_intents', payload=dict(payload), method='GET'
            )
            data = result.get('data', [])
            for intent in data:
                reference = intent.get('description')
                if not reference:
                    continue
                known = intents_by_reference.get(reference)
                if known is None or (
                    intent.get('status') == 'succeeded' and known.get('status') != 'succeeded'
                ):
                    intents_by_reference[reference] = intent
            if result.get('has_more') and data:
                payload['starting_after'] = data[-1]['id']
            else:
                break
        return intents_by_reference
