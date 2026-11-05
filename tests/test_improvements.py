import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from executionlab.stocks import Alpaca
from executionlab.live import Snapshot
from monitor import Monitor
from stock_monitor import StockMonitor
from start import validate_preferences,save_preferences,load_preferences,command


class ImprovementTests(unittest.TestCase):
    def test_batch_one_request_and_isolated_bad_symbol(self):
        calls=[]
        def opener(req,timeout):
            calls.append(req.full_url)
            return io.BytesIO(json.dumps(dict(quotes={'SPY':dict(t='2026-10-02T15:00:00Z',bp=500,ap=501,bs=3,**{'as':4},c=['R'])})).encode())
        result=Alpaca('dummy','dummy',opener=opener).quotes(['SPY','AAPL'])
        self.assertEqual(len(calls),1)
        self.assertEqual(result['SPY'].bid,500)
        self.assertIsInstance(result['AAPL'],ValueError)
        self.assertIn('SPY%2CAAPL',calls[0])

    def test_preferences_do_not_accept_secrets(self):
        with self.assertRaises(ValueError):validate_preferences({'secret':'never-store-this'})
        with self.assertRaises(ValueError):validate_preferences({'interval':float('nan')})
        with self.assertRaises(ValueError):validate_preferences({'stocks':['SPY','SPY']})

    def test_preferences_roundtrip_and_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'settings.json';settings=validate_preferences({'stocks':['AAPL']})
            save_preferences(settings,path)
            self.assertEqual(load_preferences(path),settings)
            self.assertIn('--demo',command('2',settings))
            self.assertIn('AAPL',command('1',settings))
            self.assertNotIn('--demo',command('1',settings))

    def test_rotation_preserves_old_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=Monitor(['BTC-USD'],demo=True,log_root=Path(tmp));m.rotate_bytes=1
            m.write('example',{'x':1});m.write('example',{'x':2})
            self.assertIn('1',(m.log_dir/'example.jsonl').read_text())
            self.assertIn('2',(m.log_dir/'example.001.jsonl').read_text())

    def test_health_and_duplicate_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=Monitor(['BTC-USD'],log_root=Path(tmp));now=time.time()
            s=Snapshot('BTC-USD',1,now,now,100,101,2,3)
            with patch.object(m,'get_snapshot',return_value=s):m.poll('BTC-USD');m.poll('BTC-USD')
            h=m.state()['health']['BTC-USD']
            self.assertEqual((h['accepted'],h['rejected']),(1,1))
            self.assertEqual(len((m.log_dir/'snapshots.jsonl').read_text().splitlines()),1)

    def test_batch_monitor_path(self):
        class Provider:
            feed='iex'
            def __init__(self):self.count=0
            def clock(self):
                now=time.time();return dict(is_open=True,timestamp=now,close_epoch=now+3600,session_id='one',next_open='tomorrow',next_close='today')
            def quotes(self,symbols):
                self.count+=1;now=time.time()
                return {s:Snapshot(s,self.count,now,now,100,101,2,3,'reported round lots') for s in symbols}
        with tempfile.TemporaryDirectory() as tmp:
            p=Provider();m=StockMonitor(['SPY','AAPL'],provider=p,log_root=Path(tmp));m.cycle()
            self.assertEqual(p.count,1)
            self.assertTrue(all(d.last for d in m.detectors.values()))
            self.assertIsNotNone(m.state()['batch_request_ms'])

    def test_closed_clock_throttling(self):
        class Provider:
            feed='iex'
            def __init__(self):self.count=0
            def clock(self):
                self.count+=1;return dict(is_open=False,timestamp=time.time(),close_epoch=time.time()+3600,session_id='one',next_open='next',next_close='next')
        with tempfile.TemporaryDirectory() as tmp:
            p=Provider();m=StockMonitor(['SPY'],provider=p,log_root=Path(tmp));m.cycle();m.cycle()
            self.assertEqual(p.count,1)


if __name__=='__main__':unittest.main()
