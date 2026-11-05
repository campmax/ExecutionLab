# Methodology

## Objective and units

Execute a single parent buy or sell order for one asset within a fixed session.
Quantity may be fractional. Prices and fees use the asset's quote currency.
Times are seconds on one strictly increasing numeric clock. Results are costs,
not strategy returns, Sharpe ratios or predictions.

Let s = +1 for buy and -1 for sell, Q the target quantity, q_i each fill,
p_i its price, A the first midpoint, and T the final midpoint.

```text
execution cost = s * sum(q_i * (p_i - A))
fees = sum(q_i * p_i * fee_bps / 10000)
opportunity cost = s * (Q - sum(q_i)) * (T - A)
implementation shortfall = execution cost + fees + opportunity cost
shortfall bps = 10000 * implementation shortfall / (Q * A)
cash flow = -s * sum(q_i * p_i) - fees
inventory change = s * sum(q_i)
```

Negative shortfall can occur from favorable timing or the opportunity mark. It
does not establish profitability. Filled-only price versus market VWAP is exported
as a secondary metric; it ignores incomplete quantity, so it is not the headline.
The VWAP benchmark uses all external prints in the supplied horizon and is only
computed after replay. No policy uses that future VWAP.

## Event sequence

1. At the event, process children submitted on earlier events whose delay elapsed.
2. Market children consume at most that event's displayed opposite-side depth;
   excess quantity expires (IOC). Remaining parent quantity may be resubmitted.
3. Passive activation uses a depth-based queue proxy and cannot fill from the
   activation event's print. Reject a newly arriving crossing limit (post-only).
4. Already resting passive orders expire before prints at their expiry timestamp.
   Otherwise, eligible later aggressor prints reduce queue ahead first, then fill
   the remaining quantity at its limit. No fills on quote touches alone.
5. Observe the current trade volume and make the next decision. Even zero latency
   requires a strictly later event, avoiding same-event reaction fills.
6. At the deadline, cancel pending quantity and mark missed quantity at T.

The final input timestamp is treated as a **known, prespecified deadline** for the
TWAP schedule. The CSV must cover that intended horizon. Comparing truncated inputs
changes the schedule; fix the horizon before running a causal research experiment.

## Liquidity and impact

Market fill q <= displayed touch depth D. Adverse price charge in basis points is
`impact_bps * q / D`; buy price = ask * (1 + charge/10000), sell price = bid *
(1 - charge/10000). This is an explicit assumption, not a calibrated impact model.
We model no permanent price response. All policies run independently against the
same exogenous stream; they do not compete with each other.

Displayed depth is assumed refreshed at each input event. Repeated unchanged
snapshots can overstate available liquidity. Use event-level feeds with a suitable
sampling convention and stress the assumptions. This is not a full order book.

Passive queue ahead = displayed same-side depth at activation * queue multiplier.
When the submitted price is no longer at touch, that depth is only a proxy; actual
depth at its price is unknown. Queue cancellations and newly added orders are not
inferred. Prints at or through the limit consume queue first, a simplifying rule
that does not reproduce exchange priority. Resting orders are not executed solely
because a later quote crosses them. Passive completion is particularly uncertain.

Fees are a constant notional charge, with no maker rebates or asset-specific fee
schedule. Sell simulations measure execution of an assumed available inventory;
there is no short-borrow, margin or financing model.

## Input contract

Exact UTF-8 CSV header:

```text
t,bid,ask,bid_size,ask_size,trade_price,trade_size,aggressor
```

Each row contains the current quote and one contemporaneous external print. Use
`trade_size=0,aggressor=none` for a quote-only event and supply a positive placeholder
trade_price (e.g. midpoint). Other aggressors are `buy` and `sell`, meaning the
initiator's side. Sizes share a consistent unit. Times must increase strictly;
aggregate or sequence same-time observations upstream and document the convention.
All numbers must be finite, bids positive, asks >= bids, and sizes nonnegative.
Crossed quotes, duplicate timestamps and malformed rows are rejected rather than
silently repaired. Locked quotes are allowed.

Do not manufacture bid/ask, depth or trade direction from daily OHLCV and label it
real execution data. Historical import is supported, but no licensed historical
quote dataset is bundled. There is no automatic live feed.

## Reproducibility and sources

Fixtures use Python's local `random.Random(seed)`. The demo uses seed 17. The stress
study uses seeds 0-9 independently within each engineered scenario. Input SHA256
is recorded in reports; outputs include config, fill ledger and order audit.

Conceptual references (the simulator's assumptions are defined above):
- CME TCA: https://www.cmegroup.com/education/files/TCA-4.pdf
- IBKR TWAP: https://www.interactivebrokers.com/docs/general/order-types/algorithmic-orders/ib-algorithms/twap
- IBKR POV: https://www.interactivebrokers.com/docs/general/order-types/algorithmic-orders/ib-algorithms/percentage-of-volume
