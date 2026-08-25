# -*- coding: utf-8 -*-

from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment_stripe.tests.common import StripeCommon

STRIPE_MAKE_REQUEST = (
    'odoo.addons.payment_stripe.models.payment_provider.PaymentProvider._stripe_make_request'
)


def _intent(reference, status, intent_id='pi_test_recovery', **extra):
    intent = {
        'id': intent_id,
        'status': status,
        'description': reference,
        'payment_method': {'type': 'card', 'card': {'brand': 'visa'}},
    }
    intent.update(extra)
    return intent


def _intent_list(*intents):
    return {'data': list(intents), 'has_more': False}


@tagged('post_install', '-at_install')
class TestStripeRecoveryCron(StripeCommon):

    def _backdate(self, tx, delta):
        backdated = fields.Datetime.now() - delta
        self.env.cr.execute(
            "UPDATE payment_transaction SET create_date = %s WHERE id = %s",
            (backdated, tx.id),
        )
        tx.invalidate_recordset(['create_date'])

    def test_cron_recovers_captured_transaction(self):
        """Une tx draft dont le PaymentIntent est 'succeeded' chez Stripe doit
        passer en done au passage du cron (cas webhook/redirect manqués)."""
        tx = self._create_transaction('direct', reference='TESTREC-1')
        self._backdate(tx, timedelta(minutes=30))

        with patch(
            STRIPE_MAKE_REQUEST,
            return_value=_intent_list(_intent('TESTREC-1', 'succeeded', 'pi_rec_1')),
        ), mute_logger('odoo.addons.payment_stripe_recovery.models.payment_transaction'):
            self.env['payment.transaction']._cron_stripe_recover_transactions()

        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, 'pi_rec_1')

    def test_cron_ignores_recent_transactions(self):
        """Une tx trop récente est laissée au flux nominal (webhook/redirect)."""
        tx = self._create_transaction('direct', reference='TESTREC-2')

        with patch(
            STRIPE_MAKE_REQUEST,
            return_value=_intent_list(_intent('TESTREC-2', 'succeeded')),
        ) as mock_request:
            self.env['payment.transaction']._cron_stripe_recover_transactions()

        self.assertEqual(tx.state, 'draft')
        mock_request.assert_not_called()

    def test_cron_ignores_intent_still_in_progress(self):
        """Un intent non abouti (requires_action) ne doit pas modifier la tx."""
        tx = self._create_transaction('direct', reference='TESTREC-3')
        self._backdate(tx, timedelta(hours=2))

        with patch(
            STRIPE_MAKE_REQUEST,
            return_value=_intent_list(_intent('TESTREC-3', 'requires_action')),
        ):
            self.env['payment.transaction']._cron_stripe_recover_transactions()

        self.assertEqual(tx.state, 'draft')

    def test_cron_closes_stale_abandoned_transaction(self):
        """Une tentative abandonnée (requires_payment_method) est classée en
        erreur, mais seulement après le délai de grâce."""
        recent = self._create_transaction('direct', reference='TESTREC-4')
        self._backdate(recent, timedelta(minutes=20))
        stale = self._create_transaction('direct', reference='TESTREC-5')
        self._backdate(stale, timedelta(hours=2))

        def fake_request(provider, endpoint, payload=None, method='POST', **kwargs):
            return _intent_list(
                _intent('TESTREC-4', 'requires_payment_method'),
                _intent('TESTREC-5', 'requires_payment_method'),
            )

        with patch(STRIPE_MAKE_REQUEST, fake_request), mute_logger(
            'odoo.addons.payment.models.payment_transaction'
        ):
            self.env['payment.transaction']._cron_stripe_recover_transactions()

        self.assertEqual(recent.state, 'draft')
        self.assertEqual(stale.state, 'error')

    def test_cron_survives_per_transaction_failure(self):
        """Un intent invalide sur une tx ne doit pas empêcher la récupération
        des autres (savepoint par transaction)."""
        broken = self._create_transaction('direct', reference='TESTREC-6')
        self._backdate(broken, timedelta(minutes=30))
        valid = self._create_transaction('direct', reference='TESTREC-7')
        self._backdate(valid, timedelta(minutes=30))

        broken_intent = _intent('TESTREC-6', 'succeeded')
        del broken_intent['id']  # provoque un KeyError dans _process_notification_data

        with patch(
            STRIPE_MAKE_REQUEST,
            return_value=_intent_list(
                broken_intent,
                _intent('TESTREC-7', 'succeeded', 'pi_rec_7'),
            ),
        ), mute_logger('odoo.addons.payment_stripe_recovery.models.payment_transaction'):
            self.env['payment.transaction']._cron_stripe_recover_transactions()

        self.assertEqual(broken.state, 'draft')
        self.assertEqual(valid.state, 'done')

    def test_cron_prefers_captured_intent_over_retries(self):
        """Quand plusieurs intents portent la même référence, l'intent capturé
        gagne sur les tentatives échouées, quel que soit l'ordre."""
        tx = self._create_transaction('direct', reference='TESTREC-8')
        self._backdate(tx, timedelta(minutes=30))

        with patch(
            STRIPE_MAKE_REQUEST,
            return_value=_intent_list(
                _intent('TESTREC-8', 'requires_payment_method', 'pi_rec_8a'),
                _intent('TESTREC-8', 'succeeded', 'pi_rec_8b'),
                _intent('TESTREC-8', 'requires_payment_method', 'pi_rec_8c'),
            ),
        ), mute_logger('odoo.addons.payment_stripe_recovery.models.payment_transaction'):
            self.env['payment.transaction']._cron_stripe_recover_transactions()

        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, 'pi_rec_8b')


@tagged('post_install', '-at_install')
class TestDoublePaymentGuard(StripeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.product'].create({
            'name': 'Produit test paiement',
            'type': 'consu',
            'list_price': 100.0,
            'taxes_id': [Command.clear()],
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [Command.create({
                'product_id': cls.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })

    def _order_tx_values(self, reference):
        return {
            'reference': reference,
            'amount': self.order.amount_total,
            'currency_id': self.order.currency_id.id,
            'sale_order_ids': [Command.set(self.order.ids)],
        }

    def test_blocks_new_transaction_when_order_already_paid(self):
        self._create_transaction('direct', state='done', **self._order_tx_values('TESTGUARD-1'))

        with self.assertRaises(ValidationError):
            self._create_transaction('direct', **self._order_tx_values('TESTGUARD-2'))

    def test_allows_retry_when_no_payment_captured(self):
        self._create_transaction('direct', state='draft', **self._order_tx_values('TESTGUARD-3'))
        self._create_transaction('direct', state='error', **self._order_tx_values('TESTGUARD-4'))

        tx = self._create_transaction('direct', **self._order_tx_values('TESTGUARD-5'))
        self.assertEqual(tx.state, 'draft')

    def test_allows_completing_partial_payment(self):
        values = self._order_tx_values('TESTGUARD-6')
        values['amount'] = self.order.amount_total / 2
        self._create_transaction('direct', state='done', **values)

        remainder = self._order_tx_values('TESTGUARD-7')
        remainder['amount'] = self.order.amount_total / 2
        tx = self._create_transaction('direct', **remainder)
        self.assertEqual(tx.state, 'draft')
