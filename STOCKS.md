# ExecutionLab Stocks

The stocks sister version shares the detector, dashboard, logs and local HTTP
server with the crypto monitor. It uses an Alpaca quote adapter and a market-clock
gate. It makes GET requests only and does not place orders.

## Quick start

1. Extract the entire ZIP into a writable folder.
2. Install Python 3.10 or newer with the Python launcher/PATH option.
3. To try the interface immediately, double-click `run_stocks_demo.cmd`.
4. For current stock data, create/sign in to your Alpaca account and obtain the
   API key and secret for its **paper account** from the official dashboard:
   https://app.alpaca.markets/
5. Double-click `run_stocks.cmd`. Paste the key and secret into the local terminal
   prompts. Input is hidden; nothing appears as you paste. Press Enter after each.
   This program keeps entered keys in memory, not in a file or browser response.
6. The dashboard opens at http://127.0.0.1:8766. Keep the terminal open.

No pip installation is required. Do not paste credentials into a chat or the source
code. Demo mode requires no keys. Live mode never falls back to generated data.

The default watchlist is SPY, QQQ, AAPL, MSFT and NVDA. The crypto launcher still
uses port 8765, so you can run both side by side.

## Data coverage

The default is Alpaca's **IEX feed**, which is one exchange, not a consolidated
US market feed. Quotes and liquidity can differ from consolidated quotes. The
dashboard states this limitation. It does not present IEX as nationwide NBBO.

You can select `--feed sip` if your account has the corresponding real-time SIP
entitlement. Entitlement errors remain errors; the program does not silently switch
feeds. Delayed SIP is not supported in current-detection mode. No specific pricing
plan or permanent free entitlement is assumed; check the provider's account terms.

Quotes use provider timestamps and must be fresh within 20 seconds. The app targets
five-second cycles, rather than subscribing to a tick stream. It requests the
eligible stock watchlist in one batch; slow requests can lengthen the cycle.
While closed, market-clock requests are limited to once every 30 seconds.
IEX quotes can become stale when there are no recent eligible updates. The correct
behavior then is suppression, not treating an old quote as current.

Alpaca documents quote sizes as round lots. The app preserves those reported units
and does not assume every lot equals 100 shares. Stock quote exports leave cash
notional blank because a verified symbol-specific lot conversion is not supplied.
Liquidity alerts compare the same stock's reported sizes against its own history.

## Commands

Run these from the extracted ExecutionLab folder:

```text
python stock_monitor.py
python stock_monitor.py --symbols SPY AAPL MSFT --interval 5
python stock_monitor.py --feed sip
python stock_monitor.py --price-gap-bps 15 --spread-min-bps 5
python stock_monitor.py --demo --interval 0.25
python stock_monitor.py --port 8770
```

For an existing local environment that already supplies credentials, the program
reads `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`. `--no-prompt` makes missing keys fail
instead of asking interactively. Do not put secrets into command-line arguments.

The default market-clock host is Alpaca's paper API. If using keys from a live
account, pass `--clock-account live`. That option selects only the host for the
read-only clock request; the program still has no order-sending functionality.

## Stock-specific behavior

- The provider clock controls regular-session eligibility, including holidays and
  early closes. No hand-maintained local holiday table or timezone package is needed.
- Premarket and after-hours detection is disabled. Closed sessions show the next
  provider-reported open. Leave the monitor running to resume when the market opens.
- If the clock is unavailable, stale or expired, all current stock alerts stop.
- Each regular session rebuilds each symbol's baseline. A quote must be newer than
  the moment monitoring began in that session; old opening/overnight data is ignored.
- A price change of at least 20% between accepted observations discards the prior
  baseline. This is a discontinuity guard, not a corporate-action classifier.
  It also suppresses very large genuine moves and requires a new warmup.
- Only nonzero, uncrossed, unlocked quotes whose condition list contains only `R`
  are eligible. Other conditions are conservatively rejected.
- Quotes are deduplicated using their full nanosecond timestamp. The stored
  `sequence` is a timestamp-derived token, not an exchange sequence number.

There is no dedicated halt-status or corporate-actions feed. A halt can produce a
stale or non-regular quote, which is suppressed, but this does not guarantee that
every halt is detected immediately. Overnight baseline resets limit split-related
false alerts; the monitor does not adjust historical prices for splits or dividends.

## Detector settings

Each symbol has a separate rolling median/MAD baseline with a 30-observation warmup
and a maximum of 120 observations. The current observation is excluded from its
reference. Default stock midpoint threshold is an absolute robust score of 4 and
at least a 10-bp reference gap, with a 2-bp scale floor. Default wide-spread floor is
3 bps, in addition to twice the recent median and a robust score of 4.

Thin-side alerts use displayed size below 25% of its median. Imbalance threshold is
0.8 in absolute value. Three consecutive eligible observations confirm a condition;
bad/duplicate observations break the streak. Alerts have a 60-second repeat cooldown.
Persistent price shifts recalibrate after ten consecutive breaches.

These are configurable engineering thresholds, not empirically optimized trading
signals. No fee-adjusted profit or fair-value estimate is claimed.

## Files and verification

- `stock_monitor.py`: stock launcher and session gating, sharing the monitor base.
- `executionlab/stocks.py`: Alpaca quote/clock adapters and validation.
- `tests/test_stocks.py`: 17 stock-specific tests.
- `output/monitor/<session>/`: local snapshots, alerts, errors and configuration.

All 55 tests passed (20 backtest, 18 common monitor, 17 stock). Both stock and crypto
dashboards passed local browser checks after integration. Stock checks cover the
five-symbol demo, chart selection, units, downloads, mobile width, simulated closed
market display and connection failure. No JavaScript errors occurred.

**Live authenticated Alpaca retrieval was not verified:** no user credentials were
supplied, and this build environment blocks outbound network connections. Adapter
tests use documented response shapes and mocked HTTP calls. Demo success does not
establish live-feed connectivity. API/clock errors are visible in the dashboard.

## References

- Latest quotes: https://docs.alpaca.markets/us/reference/stocklatestquotesingle-1
- Feed coverage: https://docs.alpaca.markets/us/docs/market-data-faq
- Quote fields/units: https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data
- Market clock: https://docs.alpaca.markets/us/reference/legacyclock
