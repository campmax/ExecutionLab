import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from executionlab.stocks import Alpaca, parse_quote, parse_clock, timestamp_token, validate_stock
from executionlab.live import Snapshot
from stock_monitor import StockMonitor


def raw_quote(t='2026-10-02T15:00:00.123456789Z'):
    return dict(symbol='SPY',quote=dict(t=t,bp=500,ap=500.02,bs=3,**{'as':4},bx='V',ax='V',c=['R']))


def session(now,opened=True,identity='day1'):
    return dict(is_open=opened,timestamp=now,next_open='next open',next_close='next close',
                close_epoch=now+100,session_id=identity)


class FakeProvider:
    feed='iex'
    def __init__(self):self.now=time.time();self.open=True;self.identity='day1';self.calls=0
    def clock(self):return session(self.now,self.open,self.identity)
    def quote(self,symbol):
        self.calls+=1
        return Snapshot(symbol,self.calls,self.now+.001,self.now+.001,500,500.02,3,4,'reported round lots')


class StockTests(unittest.TestCase):
    def test_quote_schema_and_lot_preservation(self):
        q=parse_quote('SPY',raw_quote(),time.time())
        self.assertEqual(q.bid_size,3)
        self.assertEqual(q.size_unit,'reported round lots')
        self.assertIsNone(q.public()['bid_notional'])

    def test_nanoseconds_not_rounded_away(self):
        a=timestamp_token('2026-10-02T15:00:00.123456788Z')
        b=timestamp_token('2026-10-02T15:00:00.123456789Z')
        self.assertEqual(b-a,1)
        self.assertEqual(b,timestamp_token('2026-10-02T11:00:00.123456789-04:00'))

    def test_quote_conditions_rejected(self):
        for c in [[],['H'],['R','N'],None,'R']:
            raw=raw_quote();raw['quote']['c']=c
            with self.assertRaises(ValueError):parse_quote('SPY',raw,time.time())

    def test_wrong_symbol_and_invalid_quote(self):
        with self.assertRaises(ValueError):parse_quote('QQQ',raw_quote(),time.time())
        for change in [dict(ap=500),dict(bp=0),dict(bs=0),dict(bp=float('nan'))]:
            raw=raw_quote();raw['quote'].update(change)
            with self.assertRaises(ValueError):parse_quote('SPY',raw,time.time())

    def test_stock_symbols(self):
        for s in ['SPY','BRK.B','AAPL']:self.assertEqual(validate_stock(s),s)
        for s in ['../secret','AAPL?x=1','aapl','BTC-USD-USD']:
            with self.assertRaises(ValueError):validate_stock(s)

    def test_clock_closed_weekend_and_early_close(self):
        now=datetime(2026,10,3,20,tzinfo=timezone.utc).timestamp()
        d=dict(timestamp='2026-10-03T16:00:00-04:00',is_open=False,
               next_open='2026-10-05T09:30:00-04:00',next_close='2026-10-05T16:00:00-04:00')
        self.assertFalse(parse_clock(d,now)['is_open'])
        d=dict(timestamp='2026-11-27T12:59:00-05:00',is_open=True,
               next_open='2026-11-30T09:30:00-05:00',next_close='2026-11-27T13:00:00-05:00')
        now=datetime.fromisoformat(d['timestamp']).timestamp()
        self.assertEqual(parse_clock(d,now)['close_epoch']-now,60)

    def test_stale_clock_blocks(self):
        d=dict(timestamp='2026-10-02T15:00:00Z',is_open=True,next_open='2026-10-05T13:30:00Z',next_close='2026-10-02T20:00:00Z')
        now=datetime.fromisoformat('2026-10-02T15:01:00+00:00').timestamp()
        with self.assertRaises(ValueError):parse_clock(d,now)

    def test_provider_only_uses_get_and_auth_headers(self):
        calls=[]
        def opener(request,timeout):
            calls.append(request)
            return io.BytesIO(json.dumps(raw_quote()).encode())
        provider=Alpaca('test-key','test-secret',opener=opener)
        provider.quote('SPY')
        self.assertEqual(calls[0].get_method(),'GET')
        self.assertTrue(calls[0].full_url.endswith('/SPY/quotes/latest?feed=iex'))
        self.assertNotIn('test-secret',calls[0].full_url)

    def test_credential_errors_redacted(self):
        def opener(*a,**kw):raise OSError('LEAK-ME key header')
        p=Alpaca('key','LEAK-ME',opener=opener)
        with self.assertRaises(ValueError) as caught:p.quote('SPY')
        self.assertNotIn('LEAK-ME',str(caught.exception))

    def test_missing_keys_and_delayed_feed_rejected(self):
        with self.assertRaises(ValueError):Alpaca('','')
        with self.assertRaises(ValueError):Alpaca('a','b',feed='delayed_sip')

    def test_closed_market_does_not_poll_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=FakeProvider();p.open=False
            m=StockMonitor(['SPY'],provider=p,log_root=Path(tmp));m.cycle()
            self.assertEqual(p.calls,0)
            self.assertEqual(m.state()['markets'][0]['status'],'market_closed')

    def test_open_cycle_and_next_day_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=FakeProvider();m=StockMonitor(['SPY'],provider=p,log_root=Path(tmp));m.cycle()
            self.assertEqual(len(m.detectors['SPY'].history),1)
            m.cycle();self.assertEqual(len(m.detectors['SPY'].history),2)
            p.identity='day2';m.cycle();self.assertEqual(len(m.detectors['SPY'].history),1)

    def test_clock_failure_pauses_all_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=FakeProvider();m=StockMonitor(['SPY','QQQ'],provider=p,log_root=Path(tmp))
            with patch.object(p,'clock',side_effect=ValueError('clock offline')):
                m.cycle();m.cycle()
            self.assertEqual(p.calls,0)
            self.assertTrue(all(x['status']=='session_unavailable' for x in m.state()['markets']))

    def test_session_expiry_suppresses_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=FakeProvider();m=StockMonitor(['SPY'],provider=p,log_root=Path(tmp));m.cycle()
            m.session['close_epoch']=time.time()-1
            self.assertFalse(m.state()['markets'][0]['fresh'])

    def test_pre_session_quote_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=FakeProvider();m=StockMonitor(['SPY'],provider=p,log_root=Path(tmp))
            with patch.object(p,'quote',return_value=Snapshot('SPY',1,p.now-1,p.now,100,101,2,3)):
                m.cycle()
            self.assertIsNone(m.detectors['SPY'].last)

    def test_large_jump_quarantines_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=FakeProvider();m=StockMonitor(['SPY'],provider=p,log_root=Path(tmp));m.cycle()
            with patch.object(p,'quote',return_value=Snapshot('SPY',2,p.now+.01,p.now+.01,250,250.01,3,4)):
                m.cycle()
            self.assertEqual(len(m.detectors['SPY'].history),1)
            self.assertFalse(m.detectors['SPY'].conditions)

    def test_stock_demo_has_no_provider_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=StockMonitor(['SPY'],demo=True,log_root=Path(tmp));m.cycle()
            self.assertEqual(m.state()['mode'],'SYNTHETIC STOCK DEMO')
            self.assertEqual(m.state()['markets'][0]['quote']['size_unit'],'reported round lots')


if __name__=='__main__':unittest.main()
