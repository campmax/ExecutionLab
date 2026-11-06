pass                                                                    
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import threading
import time
import uuid
import webbrowser
from executionlab.live import Detector, Snapshot, fetch_book, validate_symbol

ROOT = Path(__file__).resolve().parent


class Monitor:
    def __init__(self, symbols, interval=5, demo=False, log_root=None, source=None):
        self.symbols, self.interval, self.demo = symbols, interval, demo
        self.source = source or ("Generated test quotes" if demo else "Coinbase Exchange L1")
        self.detectors = {s: Detector(s) for s in symbols}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.retry = {s: 0 for s in symbols}
        self.errors = {s: 0 for s in symbols}
        self.counter = {s: 0 for s in symbols}
        self.health = {s: dict(requests=0,accepted=0,rejected=0,failures=0,last_request_ms=None) for s in symbols}
        self.rotation = {}
        self.rotate_bytes = 5_000_000
        self.log_error = None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid.uuid4().hex[:6]
        self.log_dir = (log_root or ROOT/"output"/"monitor")/stamp
        self.log_dir.mkdir(parents=True)
        self.write("session", dict(source=self.source, symbols=symbols,
                                   interval=interval, started_utc=stamp, schema_version=1,
                                   window=120, warmup=30, confirmations=3, stale_after_seconds=20))

    def write(self, kind, value):
        try:
            index=self.rotation.get(kind,0)
            path=self.log_dir/(kind+(f'.{index:03d}' if index else '')+'.jsonl')
            if path.exists() and path.stat().st_size>=self.rotate_bytes:
                index+=1
                self.rotation[kind]=index
                path=self.log_dir/(kind+f'.{index:03d}.jsonl')
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(value, allow_nan=False)+"\n")
        except OSError as exc:
            self.log_error = f"Recording failed: {exc}"

    def poll(self, symbol):
        if time.monotonic() < self.retry[symbol]:
            return
        started=time.perf_counter()
        try:
            s = self.get_snapshot(symbol)
            with self.lock:
                alerts = self.detectors[symbol].update(s)
                state = self.detectors[symbol].status
                self.errors[symbol] = 0
                h=self.health[symbol]
                h['requests']+=1
                h['last_request_ms']=(time.perf_counter()-started)*1000
                accepted=state in ('monitoring','warming_up','recalibrating')
                h['accepted' if accepted else 'rejected']+=1
                                                                      
                if state!='unchanged':self.write("snapshots", dict(s.public(), detector_status=state))
                for alert in alerts:
                    self.write("alerts", alert)
        except Exception as exc:
                                                                  
            with self.lock:
                self.detectors[symbol].fail(f"{type(exc).__name__}: {exc}")
                self.errors[symbol] += 1
                h=self.health[symbol]
                h['requests']+=1
                h['failures']+=1
                h['last_request_ms']=(time.perf_counter()-started)*1000
                delay = min(60, self.interval*2**min(self.errors[symbol], 6))
                self.retry[symbol] = time.monotonic()+delay
                self.write("errors", dict(time=time.time(), symbol=symbol, error=str(exc), retry_seconds=delay))

    def get_snapshot(self, symbol):
        if not self.demo:
            return fetch_book(symbol)
        self.counter[symbol] += 1
        n = self.counter[symbol]
        base = 60000 if symbol.startswith("BTC") else 3000
        mid = base*(1+(.003 if 35 <= n % 100 < 52 else 0))+base*.00001*math.sin(n)
        wide = 60 <= n % 100 < 65
        spread = mid*(.0005 if wide else .00001)
        now = time.time()
        return Snapshot(symbol, n, now, now, mid-spread/2, mid+spread/2, .1 if wide else 2, 2)

    def run(self):
        while not self.stop.is_set():
            started=time.monotonic()
            for symbol in self.symbols:
                if self.stop.is_set():
                    break
                self.poll(symbol)
            self.stop.wait(max(0,self.interval-(time.monotonic()-started)))

    def state(self):
        with self.lock:
            return dict(mode="SYNTHETIC DEMO" if self.demo else "LIVE PUBLIC DATA", time=time.time(),
                        source=self.source, asset="crypto", size_unit="base asset units",
                        coverage="Coinbase only; not a consolidated market feed.",
                        interval=self.interval, log_error=self.log_error,
                        health={s:dict(h,retry_seconds=max(0,self.retry[s]-time.monotonic())) for s,h in self.health.items()},
                        markets=[d.view() for d in self.detectors.values()])


def make_handler(monitor):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                payload, mime = (ROOT/"monitor_ui.html").read_bytes(), "text/html; charset=utf-8"
            elif self.path == "/api/state":
                payload, mime = json.dumps(monitor.state(), allow_nan=False).encode(), "application/json"
            elif self.path == "/report":
                payload,mime=(ROOT/'docs'/'index.html').read_bytes(),'text/html; charset=utf-8'
            elif self.path == "/tools.js":
                payload,mime=(ROOT/'monitor_tools.js').read_bytes(),'text/javascript; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass
    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbols", nargs="+", default=["BTC-USD", "ETH-USD"])
    p.add_argument("--interval", type=float, default=5)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--demo", action="store_true")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--once", action="store_true", help="One polling cycle, print status, exit")
    a = p.parse_args()
    if not math.isfinite(a.interval) or a.interval < (0.1 if a.demo else 2) or a.interval > 15:
        p.error("interval must be 2-15 seconds (demo: 0.1-15)")
    if not 1 <= len(a.symbols) <= 5 or len(set(a.symbols)) != len(a.symbols):
        p.error("Choose 1-5 distinct symbols")
    for s in a.symbols:
        validate_symbol(s)
    if not 1024 <= a.port <= 65535:
        p.error("port must be 1024-65535")
    monitor = Monitor(a.symbols, a.interval, a.demo)
    if a.once:
        for symbol in a.symbols:
            monitor.poll(symbol)
        print(json.dumps(monitor.state(), indent=2))
        return
    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(monitor))
    worker = threading.Thread(target=monitor.run, daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{a.port}"
    print(f"{url}\nMode: {'SYNTHETIC DEMO' if a.demo else 'LIVE'}\nKeep this terminal open. Ctrl+C to stop.\nLogs: {monitor.log_dir}", flush=True)
    if not a.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop.set()
        server.server_close()
        worker.join(timeout=6)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Error: {exc}")
