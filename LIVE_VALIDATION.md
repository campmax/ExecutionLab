# Live monitor validation

Build checked on 2026-10-03.

Efficiency/usability update checked later in the same local day: **62 Python tests
passed**, plus JavaScript calculator assertions. Stock and crypto browser checks
passed after the update, including search, sort, calculator, downloads, report link,
mobile layout and disconnect behavior. See `UPDATES.md` for changes.

Stock integration update: **55 total tests passed** (20 execution, 18 shared
monitor, 17 stock). The stock demo and shared crypto demo passed browser checks
after integration. See `STOCKS.md` for stock coverage and the authenticated-feed
verification limitation. The earlier crypto checks are retained below.

- 38 unit tests passed: 20 execution tests and 18 monitor tests.
- Started the actual local Python HTTP server and collector in synthetic demo mode.
- Edge browser checks passed for refreshing quotes, two market cards, chart
  selection, JSON download, and no JavaScript errors.
- Desktop dashboard screenshot visually inspected; mobile page checked at 390px
  for horizontal overflow.
- Simulated dashboard disconnection correctly disabled current detection while
  preserving historical observations.
- Demo session created recorded snapshots and confirmed alert history.
- Network adapter checked against mocked Coinbase-schema responses.

## Not verified

A direct request to the live Coinbase endpoint failed because the build workspace
blocks outbound socket access (Windows error 10013). A successful real exchange
connection and real-market detection were therefore **not verified** in this build.
Live mode is implemented but must be run on a machine/network with access to
`api.exchange.coinbase.com`. It displays errors and retries instead of substituting
demo data. The API schema was checked against official Coinbase documentation.

Windows launchers are included. Python itself and the monitor were tested on
Windows, but launcher discovery was not tested on a separate Python installation.
No trading or broker integration is included or tested.
