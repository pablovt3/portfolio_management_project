# Backtesting

The baseline includes 25 model-policy combinations: five allocation models crossed with
monthly calendar, quarterly calendar, and monthly-estimated drift bands of ±2.5, ±5 and ±7.5
percentage points. Calendar policies estimate and execute together. Band policies separate
the two decisions: targets are refreshed monthly, while the trigger is checked daily against
pre-trade weights. When any asset breaches the band, all assets return to their latest targets.

The comparison reports realized performance, the number of executed rebalances, turnover and
transaction costs. Monthly target updates that do not trigger a trade remain in the estimation
audit and do not count as rebalances.

See [methodology](methodology.md) for execution timing, cash-reference Sharpe and benchmark
costs. Run `python scripts/run_backtesting.py` for the baseline only, or
`python scripts/run_study.py` to refresh the complete publication bundle.

The baseline compares five models at two frequencies. Decisions use prior prices, execute
at the current close and affect subsequent returns. The module handles holdings, drift,
turnover and transaction costs. The project records estimation windows and target adjustments.

Published performance uses `BacktestingResult.performance()`. Calling the underlying library
comparison directly gives its scalar-rate Sharpe convention, which is not the study's
realized daily cash-reference convention. Use the project adapter for research outputs.
