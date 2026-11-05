# Results and verification

All numbers below are from generated scenarios, not historical market data.

Default: 1,000-unit buy, one-second delay, 0.5 bps fee, 2 bps impact coefficient.

| Scenario | Policy | Filled (%) | Shortfall (bps) |
|---|---|---:|---:|
| calm | immediate | 100.00 | 4.62 |
| calm | twap | 99.83 | 4.24 |
| calm | pov | 100.00 | 15.06 |
| calm | passive | 100.00 | 19.96 |
| rising | immediate | 100.00 | 5.34 |
| rising | twap | 99.83 | 49.47 |
| rising | pov | 100.00 | 35.44 |
| rising | passive | 100.00 | 40.02 |
| falling | immediate | 100.00 | 3.89 |
| falling | twap | 99.83 | -41.00 |
| falling | pov | 100.00 | -5.31 |
| falling | passive | 100.00 | 2.62 |
| liquidity_shock | immediate | 100.00 | 4.62 |
| liquidity_shock | twap | 99.83 | 15.72 |
| liquidity_shock | pov | 100.00 | 16.03 |
| liquidity_shock | passive | 100.00 | 19.85 |

## Interpretation

Cost rankings depend on the path and whether the order completes. For example,
a passive buy may miss a rising market, while a slower buy may benefit from a
falling market. These engineered paths cannot identify a generally best policy.
The stress summaries aggregate ten seeds per scenario/assumption/policy;
they are descriptive software experiments, not statistical market estimates.

## Completed validation

- 20 Python unit tests passed on the Windows runtime.
- All 960 stress replays completed and wrote finite results.
- Imported fixture replay exactly matched the generated fixture replay.
- Offline Edge checks passed: four policies, scenario/policy selection,
  CSV download, no JavaScript errors, and no page overflow at 390px width.
- Desktop report visually inspected. Mobile width checked by browser automation.
- Hand-calculated tests reconcile marked portfolio differences to shortfall.

The Windows launcher is supplied, but its Python auto-discovery was not
tested on a separate user installation. The core program was run using the
available Windows Python interpreter. No live-feed or broker test was performed.
