# Usability and efficiency update

## Added

- `START_HERE.cmd`: guided mode selector plus saved watchlists and polling settings.
  Preferences have a strict allowlist and do not accept or store API keys.
- `QUICK_START.html`: browser-friendly setup and troubleshooting guide.
- One batch stock-quote request per eligible watchlist, instead of one request per
  ticker. Individual malformed/missing quotes remain isolated.
- Stock market-clock checks reduced to once every 30 seconds while closed.
  Resumption can therefore occur up to about 30 seconds after the reported open.
- Polling waits subtract collection time, reducing drift. Slow requests may still
  lengthen a cycle; there is no attempt to catch up with bursts.
- Quote acceptance/rejection/failure counters, stock batch duration, and retry
  countdowns. Batch failures are shown separately from per-symbol processing failures.
- Duplicate snapshots are not repeatedly written. Logs rotate at approximately
  5 MB per file and preserve old segments; total recording storage is not capped.
- Ticker filtering, confirmed-condition sorting, baseline progress, alert CSV export,
  and a direct link to the original offline report.
- Hypothetical execution-cost calculator: buy/sell touch price, partial displayed
  coverage, uncovered quantity, spread cost and a user-entered fee assumption.
  No actual or simulated orders are submitted. Uncovered quantity is not assigned
  a made-up fill price, and stock lot conversion must be explicitly supplied.

## How to run

Double-click `START_HERE.cmd`. Start with option 2 (stock demo). Use option 5 to
save watchlists and settings. The original individual launchers remain available;
they use their command-line defaults, not the guided launcher's preference file.

Live stocks still need Alpaca keys. Default coverage remains IEX only; SIP requires
entitlement. Live crypto uses the public Coinbase feed. This update does not add
news forecasts, whole-market screening, trading orders or proven price predictions.

## Validation

62 Python tests pass, including new coverage for batch isolation, preferences,
log rotation, diagnostics and closed-session polling. JavaScript calculator checks
cover buy/sell accounting, partial depth, explicit stock units, invalid input and
stale/offline suppression. Browser checks passed for both stock and crypto demos:
search, sorting, cost calculation, CSV/JSON downloads, report link, mobile width,
closed-session display and disconnection suppression. No JavaScript errors occurred.
The desktop interface was also visually inspected.

Authenticated live data remains unverified: no credentials were supplied and the
execution environment blocks outbound network connections. Tests exercise mocked
provider responses and real local demo servers, not a live market connection.
