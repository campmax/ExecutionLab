# Current-data monitor

This page describes the crypto launcher. The stock sister launcher, stock-specific
thresholds and Alpaca setup are in `STOCKS.md`.

## Start

Extract the full project to a writable folder. With Python 3.10+ installed,
double-click `run_monitor.cmd`. A browser opens at http://127.0.0.1:8765.
Keep the terminal open; use Ctrl+C to stop. There are no package dependencies,
credentials or automatic trades. The interface refreshes every two seconds; the
collector targets a five-second cycle by default; slow requests can lengthen it.

Default symbols are BTC-USD and ETH-USD. Pass `--symbols` for up to five distinct
Coinbase product identifiers. These are crypto order books, not stock data.
The live polling interval can be 2-15 seconds. Slower/missing replies can reduce
sampling frequency. Failed symbols use independent exponential backoff up to 60s.

`run_monitor_demo.cmd` produces accelerated synthetic observations, visibly labeled
SYNTHETIC DEMO. Never interpret demo prices as current prices.

## Detection rules

All baselines exclude the observation being evaluated. Start with 30 accepted
observations and retain at most 120. The median resists isolated outliers. A robust
score divides deviation from the median by max(1.4826 * median absolute deviation,
a floor). Floors prevent division by zero but are assumptions, not calibration.

| Condition | Threshold |
|---|---|
| High/low midpoint | Absolute robust score >= 4 and absolute median gap >= 5 bps; price scale floor 1 bp of current mid |
| Wide spread | Spread >= 1 bp and >= twice median; robust score >= 4, scale floor 0.1 bp |
| Thin bid/ask | Displayed size at that touch < 25% of its recent median |
| Bid/ask heavy | Absolute (bid size - ask size)/(bid size + ask size) >= 0.8 |

Three consecutive eligible observations confirm a condition. A bad, stale,
duplicate or out-of-order response breaks confirmation. A condition must remain
present to appear as currently active. Confirmed alert history is separately
retained; repeat alerts for the same type have a 60-second cooldown.

Ten consecutive price-deviation breaches trigger recalibration to the latest ten
observations and another warmup. This limits repeated alerts following persistent
shifts, but may also stop flagging a genuine sustained dislocation. Thresholds are
engineering defaults and have not been calibrated against profitable outcomes.

## Freshness and limitations

Quotes older than 20 seconds, or more than five seconds ahead of the local clock,
are suppressed. Exchange and receipt timestamps are both checked. A successful
HTTP response is not itself proof of freshness. Sequences must increase and
exchange timestamps cannot go backwards. Large gaps restart the baseline.
Auctions, malformed data, crossed quotes and nonfinite values are rejected.
No synthetic fallback is used in live mode.

The dashboard marks unavailable feeds and suppresses current alerts. If its local
server connection breaks, last observations remain visibly historical, and current
detection is disabled. Keep the computer's clock synchronized.

Only the best bid and ask and their aggregate sizes are available to this monitor.
Sizes are in the base asset; notional is in the quote currency. Displayed orders
can disappear and top-of-book imbalance is not a reliable direction forecast.
Polling misses intervening events. No claim of full-depth reconstruction, executable
arbitrage, fair value, news interpretation or market-wide coverage is made.

## Recording and downloads

Every launch creates `output/monitor/<UTC-session-id>/` containing:

- `session.jsonl`: source, settings and schema version.
- `snapshots.jsonl`: normalized observed books with timestamps, sequence and status.
- `alerts.jsonl`: confirmed alerts, created when alerts occur.
- `errors.jsonl`: failures and retry delays, created when failures occur.

The dashboard download exports the currently retained observations and alert history.
Repeated duplicate snapshots are skipped. JSONL files rotate at approximately 5 MB,
and retained segments grow in total until you stop collection. A recording error
appears on the dashboard. Baselines start fresh after restart; prior logs are preserved.

These are quote snapshots, not signed trade events. Do **not** pass them directly
to the existing CSV execution simulator: that simulator needs trade events for
POV and passive fills. A historical quote anomaly study can use these recordings,
but this update does not invent missing trade data or convert them to a full tape.

## Troubleshooting

- Python not found: install Python 3.10+ with the Python launcher or PATH option.
- Address already in use: stop the earlier monitor, or run with `--port 8766`.
- Network or HTTP errors: the UI displays them; retry is automatic. Confirm that
  Coinbase Exchange's public API is reachable from your network.
- Unknown symbol: use an available Coinbase product ID such as BTC-USD.
- Persistent stale/clock error: check the system clock and exchange availability.
- A waiting or warming-up card is not a confirmed detection result.

## Verification

The full suite includes 20 execution-engine tests and 18 monitor tests. The API
adapter is tested against mocked responses matching the documented schema; tests
cover confirmation, outliers, stale quotes, sequence deduplication, rebasing,
per-symbol failures, backoff and recording. See `LIVE_VALIDATION.md` for the actual
dashboard checks and network limitations from this build.

Provider documentation:
https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book

Coinbase documents L1 as best bid/ask, aggregated size at the level, sequence and
timestamp. Polling uses that public endpoint; the implementation does not multiply
aggregated size by the number of orders.
