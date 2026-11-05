"""Read-only Coinbase L1 polling and causal robust monitoring (stdlib only)."""
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import math
import re
import statistics
import time
import urllib.request

API = "https://api.exchange.coinbase.com"


@dataclass(frozen=True)
class Snapshot:
    symbol: str
    sequence: int
    exchange_time: float
    received_time: float
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    size_unit: str = "base asset units"
    bid_venue: str = ""
    ask_venue: str = ""

    @property
    def mid(self):
        return (self.bid + self.ask) / 2

    @property
    def spread_bps(self):
        return (self.ask - self.bid) / self.mid * 10000

    def public(self):
        return dict(asdict(self), mid=self.mid, spread_bps=self.spread_bps,
                    bid_notional=self.bid*self.bid_size if self.size_unit == "base asset units" else None,
                    ask_notional=self.ask*self.ask_size if self.size_unit == "base asset units" else None)


def validate_symbol(symbol):
    if not re.fullmatch(r"[A-Z0-9]{2,12}-[A-Z0-9]{2,12}", symbol):
        raise ValueError("Use product identifiers such as BTC-USD or ETH-USD")
    return symbol


def parse_book(symbol, data, received):
    validate_symbol(symbol)
    if data.get("auction_mode"):
        raise ValueError("Auction quotes are not eligible for monitoring")
    try:
        stamp = datetime.fromisoformat(data["time"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Missing timezone")
        seq = data["sequence"]
        if isinstance(seq, bool) or int(seq) != seq or seq < 0:
            raise ValueError("Invalid sequence")
        s = Snapshot(symbol, int(seq), stamp.timestamp(), float(received),
                     float(data["bids"][0][0]), float(data["asks"][0][0]),
                     float(data["bids"][0][1]), float(data["asks"][0][1]))
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid book response: {exc}") from exc
    nums = [s.exchange_time, s.received_time, s.bid, s.ask, s.bid_size, s.ask_size]
    if not all(math.isfinite(x) for x in nums) or s.bid <= 0 or s.ask < s.bid or min(s.bid_size, s.ask_size) < 0:
        raise ValueError("Nonfinite, crossed, or invalid book")
    return s


def fetch_book(symbol, opener=None):
    validate_symbol(symbol)
    request = urllib.request.Request(f"{API}/products/{symbol}/book?level=1",
                                     headers={"User-Agent": "ExecutionLab/2.0", "Accept": "application/json", "Cache-Control": "no-cache"})
    with (opener or urllib.request.urlopen)(request, timeout=5) as response:
        body = response.read(1_000_001)
    if len(body) > 1_000_000:
        raise ValueError("Oversized response")
    return parse_book(symbol, json.loads(body), time.time())


def robust(values, value, floor):
    median = statistics.median(values)
    mad = statistics.median(abs(x-median) for x in values)
    scale = max(1.4826*mad, floor)
    return median, (value-median)/scale


class Detector:
    def __init__(self, symbol, window=120, warmup=30, stale_after=20, confirmations=3,
                 price_floor_bps=1, price_gap_bps=5, spread_min_bps=1):
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,24}", symbol):
            raise ValueError("Invalid market symbol")
        if not 5 <= warmup <= window or stale_after <= 0 or confirmations < 1:
            raise ValueError("Invalid detector configuration")
        self.symbol, self.window, self.warmup = symbol, window, warmup
        self.stale_after, self.confirmations = stale_after, confirmations
        if any(not math.isfinite(x) or x <= 0 for x in (price_floor_bps, price_gap_bps, spread_min_bps)):
            raise ValueError("Detector thresholds must be finite and positive")
        self.price_floor_bps, self.price_gap_bps, self.spread_min_bps = price_floor_bps, price_gap_bps, spread_min_bps
        self.history = deque(maxlen=window)
        self.last = None
        self.streak = {}
        self.emitted = {}
        self.conditions = []
        self.reference = None
        self.status, self.error = "waiting", None
        self.alerts = deque(maxlen=100)
        self.rebases = 0

    def fail(self, message):
        self.status, self.error = "error", str(message)[:300]
        self.streak.clear()
        self.conditions = []

    def update(self, s, now=None):
        now = time.time() if now is None else now
        if s.symbol != self.symbol:
            raise ValueError("Wrong symbol")
        age = now - s.exchange_time
        if age > self.stale_after or age < -5 or now-s.received_time > self.stale_after or now-s.received_time < -5:
            self.fail("Stale quote or clock disagreement; alerts suppressed")
            self.status = "stale"
            return []
        if self.last and (s.sequence <= self.last.sequence or s.exchange_time < self.last.exchange_time):
            self.fail("Duplicate or out-of-order book; awaiting new sequence")
            self.status = "unchanged"
            return []
        if self.last and s.exchange_time-self.last.exchange_time > self.stale_after:
            self.history.clear()
            self.streak.clear()
            self.reference = None
        self.last, self.error = s, None
        candidates = []
        if len(self.history) >= self.warmup:
            mids = [x.mid for x in self.history]
            median, z = robust(mids, s.mid, s.mid*self.price_floor_bps/10000)
            gap = (s.mid/median-1)*10000
            self.reference = dict(mid=median, gap_bps=gap, price_robust_z=z, observations=len(mids))
            if abs(z) >= 4 and abs(gap) >= self.price_gap_bps:
                candidates.append(dict(kind="price_high" if gap > 0 else "price_low",
                                       detail=f"Midpoint {gap:+.2f} bps vs recent median; robust score {z:+.1f}. This is not fair value."))
            spread_ref, spread_z = robust([x.spread_bps for x in self.history], s.spread_bps, .1)
            if s.spread_bps >= max(self.spread_min_bps, 2*spread_ref) and spread_z >= 4:
                candidates.append(dict(kind="wide_spread", detail=f"Spread {s.spread_bps:.2f} bps vs median {spread_ref:.2f} bps."))
            for side in ("bid", "ask"):
                baseline = statistics.median(getattr(x, side+"_size") for x in self.history)
                depth = getattr(s, side+"_size")
                if baseline > 0 and depth < .25*baseline:
                    candidates.append(dict(kind=f"thin_{side}", detail=f"Displayed {side} size is {depth/baseline*100:.1f}% of recent median."))
            total = s.bid_size+s.ask_size
            imbalance = (s.bid_size-s.ask_size)/total if total else 0
            if abs(imbalance) >= .8:
                candidates.append(dict(kind="bid_heavy" if imbalance > 0 else "ask_heavy",
                                       detail=f"Touch-size imbalance {imbalance:+.2f}; displayed orders can disappear."))
        else:
            self.reference = None
        kinds = {x["kind"] for x in candidates}
        self.streak = {k: self.streak.get(k, 0)+1 for k in kinds}
        self.conditions = []
        emitted = []
        for condition in candidates:
            k = condition["kind"]
            confirmed = self.streak[k] >= self.confirmations
            item = dict(condition, count=self.streak[k], confirmed=confirmed)
            self.conditions.append(item)
            if confirmed and now-self.emitted.get(k, -math.inf) >= 60:
                alert = dict(item, symbol=self.symbol, time=now, sequence=s.sequence)
                self.alerts.appendleft(alert)
                emitted.append(alert)
                self.emitted[k] = now
        self.history.append(s)
        self.status = "monitoring" if len(self.history) > self.warmup else "warming_up"
        # Sustained price shift becomes a new regime, never an everlasting bargain.
        if max(self.streak.get("price_high", 0), self.streak.get("price_low", 0)) >= 10:
            self.history = deque(list(self.history)[-10:], maxlen=self.window)
            self.streak.clear()
            self.conditions = []
            self.reference = None
            self.status = "recalibrating"
            self.rebases += 1
        return emitted

    def view(self, now=None):
        now = time.time() if now is None else now
        fresh = self.last is not None and -5 <= now-self.last.exchange_time <= self.stale_after and -5 <= now-self.last.received_time <= self.stale_after
        eligible = fresh and self.status in ("monitoring", "warming_up", "recalibrating")
        return dict(symbol=self.symbol, status=self.status if fresh or not self.last else "stale",
                    error=self.error, quote=self.last.public() if self.last else None,
                    age_seconds=max(0, now-self.last.exchange_time) if self.last else None,
                    fresh=bool(eligible), observations=len(self.history), warmup=self.warmup,
                    reference=self.reference if eligible else None,
                    conditions=self.conditions if eligible else [], alerts=list(self.alerts),
                    rebases=self.rebases,
                    chart=[dict(t=x.exchange_time, mid=x.mid, spread_bps=x.spread_bps) for x in self.history])
