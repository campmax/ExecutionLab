# ExecutionLab

**An event-driven execution backtester with a current-data anomaly monitor.**

**Start with `START_HERE.cmd`** for a guided menu and saved watchlists/settings.
Open `QUICK_START.html` for setup instructions, or
read `UPDATES.md` for the latest efficiency and usability additions.

## Stocks and crypto launchers

| What to open | Purpose | Setup |
|---|---|---|
| `run_stocks_demo.cmd` | Try the stock dashboard with synthetic data | Python 3.10+ |
| `run_stocks.cmd` | Monitor SPY, QQQ, AAPL, MSFT and NVDA | Python + Alpaca paper-account API keys |
| `run_monitor.cmd` | Monitor BTC-USD and ETH-USD | Python; no API key |
| `run_monitor_demo.cmd` | Synthetic crypto monitor demo | Python |
| `docs/index.html` | Original static execution backtest report | Browser only |

See **`STOCKS.md`** for stock setup. The stock launcher prompts locally for keys,
uses IEX quotes by default, and pauses outside regular sessions. IEX coverage is
one exchange, not the whole stock market. The stock dashboard runs on port 8766;
crypto runs on 8765. Both share the same core and can run side by side.

## New: current market monitoring

Double-click **`run_monitor.cmd`** to start the live monitor. It opens
`http://127.0.0.1:8765` and polls Coinbase's public BTC-USD and ETH-USD order books
every five seconds, plus request time. Keep the terminal open. No API key or pip
packages are required; Python 3.10+ is required.

The dashboard detects persistent price deviations, unusually wide spreads,
disappearing touch liquidity and bid/ask size imbalance. Allow roughly 2.5 minutes
for the first 30 valid observations. Quotes must be fresh, valid and have a new
sequence; confirmations require three consecutive eligible observations.

Use **`run_monitor_demo.cmd`** for a clearly labeled, accelerated synthetic demo.
Stop one monitor before starting the other, or give the second a different port.
Opening `monitor_ui.html` directly is not enough: it needs the Python monitor.
The original `docs/index.html` is still the static backtesting report.

```text
python monitor.py
python monitor.py --symbols BTC-USD ETH-USD SOL-USD --interval 5
python monitor.py --demo --interval 0.25
python monitor.py --port 8766
python monitor.py --once
```

The crypto launcher covers Coinbase products; the stocks launcher is described above.
This is read-only monitoring, not automated trading. A deviation from recent
prices does not establish fair value or a profitable opportunity. See `MONITOR.md`
for thresholds, recording, troubleshooting and verification limits.

QuantLab asks which strategy to trade. ExecutionLab asks how to complete an order
after that decision: how do urgency, spreads, delay, depth and queue position
change the actual outcome?

## Start here

1. Extract the entire ZIP.
2. Open `docs/index.html` in Chrome. The completed report works offline with no installation.
3. To run or edit the program, install Python 3.10 or newer and double-click `run_demo.cmd`.
   There are no pip packages, API keys or compiler requirements.

The included results are **synthetic engineering scenarios**, not real historical
returns. They demonstrate mechanics, not a trading edge. The separate live monitor
requests current public data; it places no broker orders.

## Commands (from this folder)

```text
python -m unittest discover -s tests -v
python run.py demo
python run.py demo --side sell --quantity 5000 --latency 5 --out output/sell
python run.py stress
python run.py replay your_quotes.csv --source "Vendor; symbol; session date; event convention" --out output/replay
```

On Windows, `py -3` can replace `python`. Rebuilding the demo overwrites `docs`
results and deterministic fixtures. Use `--out` to keep separate experiments.

## Four execution policies

| Method | Decision rule | What it teaches |
|---|---|---|
| Immediate | Submit all remaining quantity; retry after each IOC child | Urgency, spread and depth constraints |
| TWAP | Catch up to a linear schedule over a known deadline | Timing risk and completion shortfall |
| POV | Target a fraction of already observed external volume | Causal volume participation |
| Passive | Rest at the observed same-side touch; expire and repost | Queue uncertainty and missed fills |

TWAP means time-weighted average price. POV means percentage of volume. These are
simplified research implementations. In particular, POV uses cumulative external
volume, excludes our own prints, and does not impose a per-event participation cap.

## Repository

- `executionlab/engine.py`: order lifecycle, latency, fills, accounting and validation.
- `executionlab/data.py`: strict CSV import and seeded scenario generation.
- `executionlab/report.py`: offline HTML report with selectors, charts and ledger download.
- `run.py`: CLI, exports, reproducible demo and stress study.
- `monitor.py`: live collector, local dashboard server and session recording.
- `stock_monitor.py`: stock sister launcher, provider clock and session controls.
- `executionlab/stocks.py`: Alpaca stock quote and clock adapters.
- `executionlab/live.py`: public data adapter and robust anomaly detector.
- `monitor_ui.html`: auto-refreshing monitor interface.
- `tests/test_live.py`: detector, freshness, adapter and failure-handling tests.
- `tests/test_engine.py`: hand-calculated accounting, causality and lifecycle tests.
- `docs/`: precomputed report, machine-readable results and fill/audit exports.
- `data/`: all four generated event streams for inspection.
- `output/stress/`: 960 stress replay summaries (four scenarios, ten seeds,
  six assumptions, four policies).
- `METHODOLOGY.md`: equations, event semantics and model limitations.
- `RESEARCH_PLAN.md`: how to turn this engineering demo into an empirical study.

## What this adds to your portfolio

This is execution research rather than another directional return backtest. It
demonstrates event-driven architecture, order states, cash and inventory
reconciliation, transaction-cost decomposition, data validation, reproducibility
and tests designed to catch look-ahead. Python complements your existing C++ work.

An accurate description for a resume or application:

> Built an event-driven execution simulator comparing immediate, TWAP,
> volume-participation and passive policies, with configurable latency, partial
> fills, queue assumptions, transaction-cost attribution and an offline dashboard.

Do not describe the synthetic findings as validated market performance.

## Sharing

Upload the project contents with this README at the repository root. The `docs`
folder is a standalone static report suitable for repository hosting. No account
details or market-data credentials are embedded. Check licensing before uploading
any historical data you import later.
