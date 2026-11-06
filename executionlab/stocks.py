from datetime import datetime, timezone
import json
import math
import re
import time
import urllib.error
import urllib.request
import urllib.parse
from .live import Snapshot


def validate_stock(symbol):
    if not re.fullmatch(r"[A-Z][A-Z0-9]{0,9}(?:[.-][A-Z0-9]{1,3})?", symbol):
        raise ValueError("Use stock tickers such as SPY, AAPL, or BRK.B")
    return symbol


def timestamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Provider timestamp must include timezone")
    return dt


def timestamp_token(value):

    dt = timestamp(value)
    match = re.search(r"T\d{2}:\d{2}:\d{2}(?:\.(\d{1,9}))?(?:Z|[+-]\d{2}:\d{2})$", value)
    if not match:
        raise ValueError("Unsupported quote timestamp")
    return int(dt.replace(microsecond=0).timestamp())*1_000_000_000+int((match.group(1) or "").ljust(9,"0"))


def parse_quote(symbol, data, received):
    validate_stock(symbol)
    try:
        if data.get("symbol") != symbol:
            raise ValueError("Response ticker mismatch")
        q = data["quote"]
        conditions = q.get("c")
        if not isinstance(conditions,list) or not conditions or any(c != "R" for c in conditions):
            raise ValueError("Non-regular or unrecognized quote condition; detection suppressed")
        dt = timestamp(q["t"])
        result = Snapshot(symbol, timestamp_token(q["t"]), dt.timestamp(), received,
                          float(q["bp"]), float(q["ap"]), float(q["bs"]), float(q["as"]),
                          "reported round lots", str(q.get("bx", "")), str(q.get("ax", "")))
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        raise ValueError(f"Invalid stock quote: {exc}") from None
    nums = [result.bid,result.ask,result.bid_size,result.ask_size,result.received_time]
    if not all(math.isfinite(x) for x in nums) or result.bid <= 0 or result.ask <= result.bid or min(result.bid_size,result.ask_size) <= 0:
        raise ValueError("Stock quote is zero-sided, locked, crossed, or nonfinite")
    return result


def parse_clock(data, now):
    try:
        current = timestamp(data["timestamp"])
        next_open = timestamp(data["next_open"])
        next_close = timestamp(data["next_close"])
        opened = data["is_open"]
        if type(opened) is not bool:
            raise ValueError("Invalid market state")
        if not -5 <= now-current.timestamp() <= 20:
            raise ValueError("Market clock is stale or disagrees with local time")
        if next_close.timestamp() <= current.timestamp() or next_open.timestamp() <= current.timestamp():
            raise ValueError("Invalid next session boundaries")
        return dict(is_open=opened, timestamp=current.timestamp(), next_open=next_open.isoformat(),
                    next_close=next_close.isoformat(), close_epoch=next_close.timestamp(),
                    session_id=next_close.isoformat())
    except (KeyError,TypeError,ValueError,OverflowError):
        raise ValueError("Invalid/stale market clock; stock detection paused") from None


class Alpaca:
    def __init__(self, key, secret, feed="iex", clock_account="paper", opener=None):
        if not key or not secret:
            raise ValueError("Alpaca API key and secret required. Run stock_monitor.py for local setup.")
        if feed not in ("iex","sip") or clock_account not in ("paper","live"):
            raise ValueError("Unsupported Alpaca feed or clock account")
        self._key, self._secret = key, secret
        self.feed, self.clock_account = feed, clock_account
        self._open = opener or urllib.request.urlopen

    def _get(self, url):
        request = urllib.request.Request(url, headers={"APCA-API-KEY-ID":self._key,
                    "APCA-API-SECRET-KEY":self._secret,"User-Agent":"ExecutionLab/3.0","Accept":"application/json"})
        try:
            with self._open(request,timeout=5) as response:
                body=response.read(1_000_001)
            if len(body)>1_000_000:
                raise ValueError("Oversized response")
            return json.loads(body)
        except urllib.error.HTTPError as exc:

            meaning={401:"check API keys and account selection",403:"check feed entitlement and account selection",429:"rate limited; automatic retry"}.get(exc.code,"provider request failed")
            raise ValueError(f"Alpaca HTTP {exc.code}: {meaning}") from None
        except Exception:
            raise ValueError("Alpaca request failed: network unavailable or invalid response") from None

    def quote(self, symbol):
        validate_stock(symbol)
        data=self._get(f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest?feed={self.feed}")
        return parse_quote(symbol,data,time.time())

    def clock(self):
        host="paper-api.alpaca.markets" if self.clock_account=="paper" else "api.alpaca.markets"
        return parse_clock(self._get(f"https://{host}/v2/clock"),time.time())

    def quotes(self, symbols):
        for symbol in symbols:validate_stock(symbol)
        query=urllib.parse.urlencode(dict(symbols=','.join(symbols),feed=self.feed))
        data=self._get('https://data.alpaca.markets/v2/stocks/quotes/latest?'+query)
        if not isinstance(data,dict) or not isinstance(data.get('quotes'),dict):
            raise ValueError('Invalid batch quote response')
        received=time.time()
        result={}
        for symbol in symbols:
            try:
                result[symbol]=parse_quote(symbol,dict(symbol=symbol,quote=data['quotes'][symbol]),received)
            except Exception:
                result[symbol]=ValueError('Missing or ineligible quote in batch response')
        return result
