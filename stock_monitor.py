"""Stocks sister launcher. No trading endpoints. Reuses Monitor and Detector."""
import argparse
from dataclasses import replace
import getpass
from http.server import ThreadingHTTPServer
import math
import os
import threading
import time
import webbrowser
from executionlab.live import Detector, Snapshot
from executionlab.stocks import Alpaca, validate_stock
from monitor import Monitor, make_handler


class StockMonitor(Monitor):
    def __init__(self, symbols, interval=5, demo=False, log_root=None, provider=None,
                 price_gap_bps=10, spread_min_bps=3):
        for symbol in symbols:validate_stock(symbol)
        if not demo and provider is None:raise ValueError("Stock provider required")
        self.provider=provider
        self.feed=provider.feed if provider else "demo"
        source="Generated stock test quotes" if demo else f"Alpaca {self.feed.upper()} quotes"
        super().__init__(symbols,interval,demo,log_root,source=source)
        self.price_gap_bps,self.spread_min_bps=price_gap_bps,spread_min_bps
        self.detectors={s:self.new_detector(s) for s in symbols}
        self.session=None
        self.session_start=None
        self.session_id=None
        self.clock_retry=0
        self.clock_errors=0
        self.session_error=None
        self.batch=None
        self.batch_retry=0
        self.batch_errors=0
        self.batch_ms=None
        self.write("session",dict(asset="stocks",feed=self.feed,size_unit="reported round lots",
                                   regular_hours_only=True,price_gap_bps=price_gap_bps,
                                   spread_min_bps=spread_min_bps,price_floor_bps=2))

    def new_detector(self,symbol):
        return Detector(symbol,price_floor_bps=2,price_gap_bps=self.price_gap_bps,spread_min_bps=self.spread_min_bps)

    def pause(self,status,message):
        with self.lock:
            for d in self.detectors.values():
                d.fail(message)
                d.status=status

    def cycle(self):
        if self.demo:
            self.session=dict(is_open=True,timestamp=time.time(),next_open="demo",next_close="demo",close_epoch=time.time()+60)
        else:
            if time.monotonic()<self.clock_retry:return
            try:
                session=self.provider.clock()
                with self.lock:
                    self.session=session
                    self.session_error=None
                    self.clock_errors=0
                    if session["is_open"] and session["session_id"]!=self.session_id:
                        self.session_id=session["session_id"]
                        self.session_start=session["timestamp"]
                        # Preserve alert history, but never mix prior-day baselines.
                        for symbol,d in list(self.detectors.items()):
                            fresh=self.new_detector(symbol)
                            fresh.alerts=d.alerts
                            self.detectors[symbol]=fresh
                        self.retry={s:0 for s in self.symbols}
                        self.write("session_transitions",dict(time=time.time(),session=self.session_id))
                if not session["is_open"]:
                    self.pause("market_closed","Regular stock session closed; waiting for next open")
                    # No need to ask the clock every five seconds overnight.
                    self.clock_retry=time.monotonic()+30
                    return
            except Exception as exc:
                self.session_error=str(exc)
                self.clock_errors+=1
                delay=min(60,self.interval*2**min(self.clock_errors,6))
                self.clock_retry=time.monotonic()+delay
                self.pause("session_unavailable","Cannot verify market hours; detection paused")
                self.write("errors",dict(time=time.time(),component="market_clock",error=str(exc),retry_seconds=delay))
                return
        self.batch=None
        if not self.demo and hasattr(self.provider,'quotes'):
            if time.monotonic()<self.batch_retry:return
            try:
                started=time.perf_counter()
                eligible=[s for s in self.symbols if time.monotonic()>=self.retry[s]]
                if not eligible:return
                self.batch=self.provider.quotes(eligible)
                self.batch_ms=(time.perf_counter()-started)*1000
                self.batch_errors=0
            except Exception as exc:
                self.batch_errors+=1
                delay=min(60,self.interval*2**min(self.batch_errors,6))
                self.batch_retry=time.monotonic()+delay
                self.pause('error',str(exc))
                self.write('errors',dict(time=time.time(),component='batch_quotes',error=str(exc),retry_seconds=delay))
                return
        try:
            for symbol in (list(self.batch) if self.batch is not None else self.symbols):
                if self.stop.is_set():break
                self.poll(symbol)
        finally:self.batch=None

    def poll(self,symbol):
        # Recheck clock freshness before each potentially slow quote request.
        now=time.time()
        if not self.demo and (not self.session or self.session_error or not self.session["is_open"] or
                              now-self.session["timestamp"]>20 or now>=self.session["close_epoch"]):
            self.pause("session_unavailable","Session not verified open; detection paused")
            return
        super().poll(symbol)

    def get_snapshot(self,symbol):
        if self.demo:
            s=super().get_snapshot(symbol)
            base={"SPY":550,"QQQ":470,"AAPL":220,"MSFT":430,"NVDA":125}.get(symbol,100)
            ratio=base/3000
            return replace(s,bid=s.bid*ratio,ask=s.ask*ratio,bid_size=s.bid_size*10,
                           ask_size=s.ask_size*10,size_unit="reported round lots",bid_venue="demo",ask_venue="demo")
        s=self.batch[symbol] if self.batch is not None else self.provider.quote(symbol)
        if isinstance(s,Exception):raise s
        now=time.time()
        if now-self.session["timestamp"]>20 or now>=self.session["close_epoch"]:
            raise ValueError("Market session expired during quote request")
        if s.exchange_time<self.session_start:
            raise ValueError("Waiting for a quote after this session's monitoring start")
        d=self.detectors[symbol]
        # Quarantine large discontinuities without declaring them corporate actions.
        if d.last and abs(s.mid/d.last.mid-1)>=.2:
            with self.lock:
                fresh=self.new_detector(symbol)
                fresh.alerts=d.alerts
                self.detectors[symbol]=fresh
                self.write("data_quality",dict(time=now,symbol=symbol,reason="20% price discontinuity; baseline reset"))
        return s

    def run(self):
        while not self.stop.is_set():
            started=time.monotonic()
            self.cycle()
            self.stop.wait(max(0,self.interval-(time.monotonic()-started)))

    def state(self):
        result=super().state()
        now=time.time()
        result.update(asset="stocks",size_unit="reported round lots",
                      batch_request_ms=self.batch_ms,batch_retry_seconds=max(0,self.batch_retry-time.monotonic()),
                      mode="SYNTHETIC STOCK DEMO" if self.demo else "LIVE STOCK DATA",
                      coverage=("Synthetic stock observations; no live data." if self.demo else
                                "IEX ONLY — one exchange, not consolidated NBBO." if self.feed=="iex" else
                                "SIP consolidated quotes — requires corresponding Alpaca entitlement."),
                      session=self.session,session_error=self.session_error,
                      thresholds=dict(price_gap_bps=self.price_gap_bps,spread_min_bps=self.spread_min_bps))
        good=self.demo or (self.session and not self.session_error and self.session["is_open"] and
                          -5<=now-self.session["timestamp"]<=20 and now<self.session["close_epoch"])
        if not good:
            closed=self.session and not self.session["is_open"] and not self.session_error
            for m in result["markets"]:
                m.update(fresh=False,conditions=[],reference=None,status="market_closed" if closed else "session_unavailable")
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbols",nargs="+",default=["SPY","QQQ","AAPL","MSFT","NVDA"])
    p.add_argument("--interval",type=float,default=5)
    p.add_argument("--port",type=int,default=8766)
    p.add_argument("--feed",choices=["iex","sip"],default="iex")
    p.add_argument("--clock-account",choices=["paper","live"],default="paper")
    p.add_argument("--price-gap-bps",type=float,default=10)
    p.add_argument("--spread-min-bps",type=float,default=3)
    p.add_argument("--demo",action="store_true")
    p.add_argument("--no-browser",action="store_true")
    p.add_argument("--no-prompt",action="store_true")
    a=p.parse_args()
    if not 1<=len(a.symbols)<=5 or len(set(a.symbols))!=len(a.symbols):p.error("Choose 1-5 distinct stock symbols")
    for symbol in a.symbols:validate_stock(symbol)
    if not math.isfinite(a.interval) or not (.1 if a.demo else 2)<=a.interval<=15:p.error("Interval must be 2-15s (demo: .1-15s)")
    if not 1024<=a.port<=65535:p.error("Port must be 1024-65535")
    for threshold in (a.price_gap_bps,a.spread_min_bps):
        if not math.isfinite(threshold) or threshold<=0:p.error("Thresholds must be finite and positive")
    provider=None
    if not a.demo:
        key=os.environ.get("ALPACA_API_KEY","")
        secret=os.environ.get("ALPACA_SECRET_KEY","")
        if not (key and secret) and not a.no_prompt:
            print("Enter Alpaca PAPER account keys locally. Input is hidden and not saved.\nUse --clock-account live only for live-account keys. No orders are sent.")
            key=key or getpass.getpass("API key: ").strip()
            secret=secret or getpass.getpass("Secret key: ").strip()
        provider=Alpaca(key,secret,a.feed,a.clock_account)
    m=StockMonitor(a.symbols,a.interval,a.demo,provider=provider,price_gap_bps=a.price_gap_bps,spread_min_bps=a.spread_min_bps)
    server=ThreadingHTTPServer(("127.0.0.1",a.port),make_handler(m))
    worker=threading.Thread(target=m.run,daemon=True);worker.start()
    url=f"http://127.0.0.1:{a.port}"
    print(f"{url}\n{'SYNTHETIC STOCK DEMO' if a.demo else 'STOCKS / '+a.feed.upper()}\nKeep terminal open. Ctrl+C to stop.",flush=True)
    if not a.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        m.stop.set();server.server_close();worker.join(timeout=6)


if __name__=="__main__":
    try:main()
    except (ValueError,OSError,EOFError) as exc:raise SystemExit(f"Error: {exc}")
