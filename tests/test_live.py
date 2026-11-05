import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from executionlab.live import Snapshot, Detector, parse_book, fetch_book
from monitor import Monitor


def quote(n, mid=100, spread=.01, bid_size=10, ask_size=10):
    return Snapshot('BTC-USD', n, float(n), float(n), mid-spread/2, mid+spread/2, bid_size, ask_size)


def warmed():
    d=Detector('BTC-USD')
    for i in range(1,32):
        d.update(quote(i), now=i)
    return d


class LiveTests(unittest.TestCase):
    def test_parse_real_api_shape(self):
        d=dict(sequence=10,time='2026-10-03T22:00:00.123Z',bids=[['60000','2',5]],asks=[['60001','3',7]])
        s=parse_book('BTC-USD',d,1791064800)
        self.assertEqual(s.bid_size,2)  # Never multiply aggregate size by order count.
        self.assertEqual(s.ask_size,3)

    def test_invalid_auction_crossed_missing_time(self):
        base=dict(sequence=1,time='2026-10-03T22:00:00Z',bids=[['100','2']],asks=[['101','3']])
        for change in [dict(auction_mode=True),dict(asks=[['99','3']]),dict(time='bad'),dict(bids=[]),dict(sequence=1.5),dict(bids=[['nan','2']])]:
            with self.assertRaises(ValueError):parse_book('BTC-USD',dict(base,**change),1)

    def test_no_alert_during_warmup(self):
        d=Detector('BTC-USD')
        for i in range(1,30):self.assertEqual(d.update(quote(i,mid=100+i),now=i),[])

    def test_confirmation_requires_three(self):
        d=warmed()
        self.assertFalse(d.update(quote(32,mid=101),now=32))
        self.assertFalse(d.update(quote(33,mid=101),now=33))
        self.assertIn('price_high',[x['kind'] for x in d.update(quote(34,mid=101),now=34)])

    def test_single_outlier_not_confirmed(self):
        d=warmed();d.update(quote(32,mid=105),now=32)
        self.assertFalse(d.update(quote(33),now=33))
        self.assertEqual(d.conditions,[])
        self.assertAlmostEqual(d.reference['mid'],100)

    def test_current_quote_excluded_from_reference(self):
        d=warmed();d.update(quote(32,mid=500),now=32)
        self.assertEqual(d.reference['mid'],100)

    def test_repeated_sequence_cannot_confirm(self):
        d=warmed();d.update(quote(32,mid=101),now=32)
        for n in range(3):self.assertFalse(d.update(quote(32,mid=101),now=33+n))
        self.assertEqual(len(d.history),32)
        self.assertFalse(d.view(now=35)['conditions'])

    def test_stale_and_future_quotes_rejected(self):
        d=warmed()
        self.assertFalse(d.update(quote(32),now=60))
        self.assertFalse(d.update(quote(100),now=60))
        self.assertEqual(d.last.sequence,31)

    def test_view_expires_without_another_update(self):
        d=warmed()
        self.assertEqual(d.view(now=60)['status'],'stale')
        self.assertFalse(d.view(now=60)['fresh'])

    def test_error_suppresses_conditions(self):
        d=warmed()
        for i in range(32,35):d.update(quote(i,mid=101),now=i)
        d.fail('network unavailable')
        self.assertFalse(d.view(now=35)['fresh'])
        self.assertEqual(d.view(now=35)['conditions'],[])
        self.assertTrue(d.view(now=35)['alerts'])

    def test_gap_restarts_warmup(self):
        d=warmed();d.update(quote(100,mid=110),now=100)
        self.assertEqual(len(d.history),1)
        self.assertIsNone(d.reference)

    def test_persistent_shift_recalibrates(self):
        d=warmed()
        for i in range(32,42):d.update(quote(i,mid=110),now=i)
        self.assertEqual(d.rebases,1)
        self.assertEqual(d.status,'recalibrating')
        self.assertEqual(len(d.history),10)

    def test_wide_spread_thin_depth_imbalance(self):
        d=warmed()
        alerts=[]
        for i in range(32,35):alerts+=d.update(quote(i,spread=.2,bid_size=.1),now=i)
        kinds={x['kind'] for x in alerts}
        self.assertTrue({'wide_spread','thin_bid','ask_heavy'}<=kinds)

    def test_constant_zero_mad_safe(self):
        d=warmed();d.update(quote(32),now=32)
        self.assertEqual(d.reference['price_robust_z'],0)
        json.dumps(d.view(now=32),allow_nan=False)

    def test_alert_cooldown(self):
        d=warmed();alerts=[]
        for i in range(32,40):alerts+=d.update(quote(i,spread=.2),now=i)
        self.assertEqual(len([x for x in alerts if x['kind']=='wide_spread']),1)

    def test_mocked_http_adapter(self):
        body=dict(sequence=1,time='2026-10-03T22:00:00Z',bids=[['100','2']],asks=[['101','3']])
        def opener(request,timeout):
            self.assertTrue(request.full_url.endswith('/BTC-USD/book?level=1'))
            self.assertEqual(timeout,5)
            return io.BytesIO(json.dumps(body).encode())
        self.assertEqual(fetch_book('BTC-USD',opener).mid,100.5)

    def test_backoff_and_symbol_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=Monitor(['BTC-USD','ETH-USD'],log_root=Path(tmp))
            with patch('monitor.fetch_book',side_effect=OSError('offline')) as fetch:
                m.poll('BTC-USD');m.poll('BTC-USD')
                self.assertEqual(fetch.call_count,1)
                self.assertEqual(m.detectors['ETH-USD'].status,'waiting')
            self.assertEqual(m.detectors['BTC-USD'].status,'error')

    def test_demo_recording_and_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=Monitor(['BTC-USD'],demo=True,log_root=Path(tmp));m.poll('BTC-USD')
            self.assertEqual(m.state()['mode'],'SYNTHETIC DEMO')
            self.assertTrue((m.log_dir/'snapshots.jsonl').is_file())


if __name__=='__main__':unittest.main()
