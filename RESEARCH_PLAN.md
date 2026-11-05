# From engineering demo to execution research

## Research question

For a fixed symbol, side, arrival time, size and deadline, how do execution policy
and urgency affect implementation shortfall and completion? Analyze both jointly.

## Data and pre-registration

Obtain appropriately licensed historical quotes, displayed sizes and signed trades.
Document timezone, market sessions, tick/lot sizes, quote/trade alignment, missing
intervals and aggressor classification. Preserve raw files, normalized files and
hashes. Choose an asset with reliable coverage rather than inventing depth.

Define parent orders without future returns: for example, prespecified timestamps
and sizes based only on earlier sessions' volume. Randomize or balance buy/sell
direction. Fix horizons before replay and avoid orders spanning data gaps.

## Development and evaluation

Split chronologically by whole day. Use development days to choose queue, delay,
participation and fee assumptions. Freeze the code and parameter grid before
opening evaluation days. Do not tune a winning policy separately on each test day.

Report paired policy differences for identical parent orders. Include medians,
tail shortfall, fill rates, unfilled quantities, fees and results by volatility,
spread and size bucket. Bootstrap paired differences by day, not individual fills,
because nearby executions are dependent. This statistical evaluation is a next
research phase, not something the synthetic demo claims to have completed.

## Stress and falsification

The bundled 960-run study changes one assumption at a time: fee x4, latency 5s,
queue x3, size x5 and impact x3, plus base. Ten seeds and four engineered regimes
test stability of the software and sensitivity to assumptions. They are not
out-of-sample historical validation or confidence intervals about real markets.

For historical research add joint stresses, sparse/stale feeds, tick rounding,
fees by venue, alternative queue models, and a richer book model. Compare the
passive model with actual small-order paper/live observations if available and
authorized. Large sensitivity to queue assumptions is itself a useful finding.

## What to explain in an interview

1. Why same-event fills can leak information.
2. Why fill-only average price can flatter an algorithm that barely trades.
3. How paper portfolio value minus actual marked value reconciles to shortfall.
4. Why historical replay cannot identify counterfactual market impact by itself.
5. Which assumptions require full order-book data and which can be tested here.
