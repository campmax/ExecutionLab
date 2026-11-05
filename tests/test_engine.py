import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from executionlab.engine import Event, Config, simulate, validate_events, POLICIES
from executionlab.data import scenario, write_events, read_events


def event(t, bid=99, ask=101, depth=10, volume=0, aggressor="none", price=100):
    return Event(t, bid, ask, depth, depth, price, volume, aggressor)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.c = Config(quantity=10, fee_bps=0, impact_bps=0)

    def test_buy_uses_future_ask(self):
        r = simulate([event(0), event(1, 101, 103)], "immediate", self.c)
        self.assertEqual(r["fills"][0]["price"], 103)
        self.assertEqual(r["summary"]["shortfall"], 30)

    def test_sell_sign(self):
        r = simulate([event(0), event(1, 97, 99)], "immediate", replace(self.c, side="sell"))
        self.assertEqual(r["summary"]["shortfall"], 30)
        self.assertEqual(r["summary"]["cash_flow"], 970)
        self.assertEqual(r["summary"]["inventory_change"], -10)

    def test_zero_latency_still_later_event(self):
        r = simulate([event(0), event(1)], "immediate", replace(self.c, latency=0))
        self.assertEqual(r["fills"][0]["t"], 1)

    def test_latency_blocks_early_fill(self):
        r = simulate([event(0), event(1), event(2)], "immediate", replace(self.c, latency=2))
        self.assertEqual(r["fills"][0]["t"], 2)

    def test_partial_fill_and_opportunity(self):
        r = simulate([event(0), event(1, 101, 103, depth=4)], "immediate", self.c)["summary"]
        self.assertEqual(r["filled"], 4)
        self.assertEqual(r["execution_cost"], 12)
        self.assertEqual(r["opportunity_cost"], 12)
        self.assertEqual(r["shortfall"], 24)

    def test_no_depth_no_fills(self):
        r = simulate([event(0), event(1, depth=0)], "immediate", self.c)
        self.assertEqual(r["summary"]["filled"], 0)
        self.assertIsNone(r["summary"]["average_price"])

    def test_fee_is_notional_based(self):
        r = simulate([event(0), event(1)], "immediate", replace(self.c, fee_bps=10))["summary"]
        self.assertAlmostEqual(r["fees"], 1.01)
        self.assertAlmostEqual(r["cash_flow"], -1011.01)

    def test_impact_is_adverse_both_sides(self):
        for side in ("buy", "sell"):
            base = simulate([event(0), event(1)], "immediate", replace(self.c, side=side))["summary"]
            costly = simulate([event(0), event(1)], "immediate", replace(self.c, side=side, impact_bps=5))["summary"]
            self.assertGreater(costly["shortfall"], base["shortfall"])

    def test_passive_queue_and_activation(self):
        es = [event(0), event(1, volume=100, aggressor="sell", price=99),
              event(2, volume=7, aggressor="sell", price=99),
              event(3, volume=8, aggressor="sell", price=99)]
        r = simulate(es, "passive", self.c)
        self.assertEqual(len(r["fills"]), 1)
        self.assertEqual(r["fills"][0]["quantity"], 5)
        self.assertEqual(r["fills"][0]["t"], 3)

    def test_passive_wrong_aggressor_no_fill(self):
        es = [event(0), event(1), event(2, volume=100, aggressor="buy", price=99)]
        self.assertFalse(simulate(es, "passive", self.c)["fills"])

    def test_passive_sell_queue(self):
        es = [event(0), event(1), event(2, volume=14, aggressor="buy", price=101)]
        r = simulate(es, "passive", replace(self.c, side="sell"))
        self.assertEqual(r["summary"]["filled"], 4)
        self.assertEqual(r["fills"][0]["price"], 101)

    def test_post_only_reject(self):
        es = [event(0), event(1, bid=97, ask=98)]
        r = simulate(es, "passive", self.c)
        self.assertIn("post_only_reject", [x["action"] for x in r["audit"]])
        self.assertFalse(r["fills"])

    def test_expiry_before_trade(self):
        es = [event(0), event(1), event(3, volume=100, aggressor="sell", price=99)]
        r = simulate(es, "passive", replace(self.c, passive_ttl=2))
        self.assertFalse(r["fills"])

    def test_pov_does_not_anticipate_volume(self):
        es = [event(0), event(1, volume=100, aggressor="buy", price=101), event(2)]
        r = simulate(es, "pov", self.c)
        self.assertEqual(r["fills"][0]["t"], 2)
        self.assertEqual(r["fills"][0]["decision_t"], 1)

    def test_future_prices_cannot_change_past_orders(self):
        a = scenario(n=61)
        b = a[:31] + [replace(e, bid=e.bid+10, ask=e.ask+10, trade_price=e.trade_price+10) for e in a[31:]]
        for policy in POLICIES:
            x = simulate(a, policy, self.c)
            y = simulate(b, policy, self.c)
            self.assertEqual([r for r in x["audit"] if r["t"] <= 30], [r for r in y["audit"] if r["t"] <= 30])

    def test_conservation_and_reconciliation(self):
        for side in ("buy", "sell"):
            for policy in POLICIES:
                c = replace(self.c, side=side, quantity=123, fee_bps=.7)
                r = simulate(scenario(n=101), policy, c)
                s = r["summary"]
                self.assertLessEqual(s["filled"], c.quantity+1e-8)
                self.assertAlmostEqual(s["filled"], sum(f["quantity"] for f in r["fills"]))
                self.assertAlmostEqual(s["shortfall"], s["execution_cost"]+s["fees"]+s["opportunity_cost"])
                sign = 1 if side == "buy" else -1
                # Paper marked portfolio minus actual marked portfolio equals IS.
                paper = sign*c.quantity*(s["terminal"]-s["arrival"])
                actual = s["cash_flow"]+s["inventory_change"]*s["terminal"]
                self.assertAlmostEqual(paper-actual, s["shortfall"])
                self.assertTrue(all(f["t"] > f["decision_t"] for f in r["fills"]))

    def test_csv_roundtrip(self):
        es = scenario(n=4)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"events.csv"
            write_events(p, es)
            self.assertEqual(read_events(p), es)

    def test_bad_quotes_and_times_rejected(self):
        for bad in [event(0), event(1,bid=103,ask=100), event(1,depth=-1), event(1,bid=math.nan), event(1,volume=2)]:
            with self.assertRaises(ValueError):
                validate_events([event(0), bad])

    def test_bad_config(self):
        for c in [replace(self.c, quantity=0), replace(self.c, latency=-1), replace(self.c, participation=2), replace(self.c, fee_bps=math.inf)]:
            with self.assertRaises(ValueError):
                c.validate()

    def test_fee_sensitivity_exact(self):
        es = scenario(n=80)
        x = simulate(es, "immediate", self.c)
        y = simulate(es, "immediate", replace(self.c, fee_bps=5))
        self.assertAlmostEqual(y["summary"]["shortfall"]-x["summary"]["shortfall"], y["summary"]["fees"])
        self.assertEqual(x["summary"]["filled"], y["summary"]["filled"])


if __name__ == "__main__":
    unittest.main()
