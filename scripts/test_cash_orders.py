"""Offline checks only: no network, credentials, browser or real broker calls."""
import importlib.util
from pathlib import Path
import random
from types import SimpleNamespace as NS
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'examples' / 'cash-orders.py'


class CashOrdersTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('cash_orders', SOURCE)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)
        self.orders = []
        self.cancelled = []
        self.helper.log = NS(info=lambda message: None)
        self.helper.order = self.submit
        self.helper.cancel_order = self.cancelled.append

    def submit(self, asset, amount, **kwargs):
        self.orders.append((asset, amount, kwargs))
        return len(self.orders)

    def account(self, cash=20000, q=800, t=0):
        return NS(qqq='QQQ', tqqq='TQQQ', days=10, pending=[],
                  portfolio=NS(cash=cash, positions={
                      'QQQ': NS(amount=q), 'TQQQ': NS(amount=t)}))

    def test_sell_proceeds_are_not_spent_before_confirmation(self):
        c = self.account()
        self.helper.rebalance(c, 100, 50, 0.6)
        self.assertEqual([(a, n) for a, n, _ in self.orders], [('QQQ', -402)])
        # Cash receipt is a separate later event; pending IDs prevent replacement.
        self.helper.rebalance(c, 100, 50, 0.6)
        self.assertEqual(len(self.orders), 1)

    def test_cash_received_after_sell_can_fund_buy(self):
        c = self.account(cash=60300, q=397)
        self.helper.rebalance(c, 100, 50, 0.6)
        self.assertTrue(any(n > 0 for _, n, _ in self.orders))
        self.assertTrue(all(n > 0 for _, n, _ in self.orders))

    def test_joint_limit_budget_for_many_account_states(self):
        rng = random.Random(20261017)
        for _ in range(2000):
            self.orders.clear()
            cash = rng.uniform(25, 200000)
            q, t = rng.randint(0, 1000), rng.randint(0, 1000)
            qp, tp = rng.uniform(15, 650), rng.uniform(10, 250)
            c = self.account(cash, q, t)
            self.helper.rebalance(c, qp, tp, rng.choice([0, .1, .3, .4, .6, .7]))
            buys = [(a, n, k) for a, n, k in self.orders if n > 0]
            sells = [(a, n, k) for a, n, k in self.orders if n < 0]
            self.assertFalse(buys and sells)
            equity = cash + q * qp + t * tp
            spend = sum(n * k['limit_price'] for _, n, k in buys)
            self.assertLessEqual(spend, max(0, cash - max(20, equity * .005)) + 1e-7)
            for _, n, k in buys:
                self.assertEqual(k['style'], 'limit')
                self.assertIsInstance(n, int)

    def test_price_gap_does_not_expand_reserved_buy_amount(self):
        c = self.account(cash=100000, q=0)
        self.helper.rebalance(c, 100, 50, 0)
        _, quantity, params = self.orders[0]
        cap = params['limit_price']
        self.assertLessEqual(quantity * cap, 99500)
        # A next-bar opening gap above the cap cannot be filled at that opening
        # by the stub; the order stays open until cancellation is confirmed.
        next_open = 130
        self.assertGreater(next_open, cap)
        self.helper.get_order = lambda _: NS(status=5)
        self.helper.check_orders(c)
        self.assertEqual(c.pending, [1])
        self.assertEqual(self.cancelled, [1])
        self.helper.rebalance(c, next_open, 50, 0)
        self.assertEqual(len(self.orders), 1)

    def test_partial_fill_and_async_cancellation_remain_tracked(self):
        c = self.account()
        c.pending = [7]
        self.helper.get_order = lambda _: NS(status=9, filled=2)
        self.helper.check_orders(c)
        self.assertEqual(c.pending, [7])
        self.assertEqual(self.cancelled, [7])
        self.helper.get_order = lambda _: NS(status=4)
        self.helper.check_orders(c)
        self.assertEqual(c.pending, [])

    def test_fill_during_cancellation_is_terminal(self):
        c = self.account()
        c.pending = [7]
        self.helper.get_order = lambda _: NS(status=6)
        self.helper.check_orders(c)
        self.assertEqual(c.pending, [])
        self.assertEqual(self.cancelled, [])

    def test_rejected_missing_and_unknown_orders_are_not_hidden(self):
        for ticket in [NS(status=8, reason='Test rejection'), None, NS(status=99)]:
            c = self.account()
            c.pending = [7]
            self.helper.get_order = lambda _, value=ticket: value
            with self.assertRaises(ValueError):
                self.helper.check_orders(c)

    def test_negative_cash_and_invalid_prices_stop(self):
        with self.assertRaises(ValueError):
            self.helper.rebalance(self.account(cash=-5), 100, 50, .3)
        for price in [0, -1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                self.helper.rebalance(self.account(), price, 50, .3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
