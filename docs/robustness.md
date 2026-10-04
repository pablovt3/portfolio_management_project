# Robustness

The baseline policy comparison includes three predeclared drift bands: ±2.5, ±5 and ±7.5
percentage points. This grid is the sensitivity analysis for the execution threshold. Cost
scenarios retain every calendar and band portfolio because transaction costs are central to
the policy choice. Lookback and position-cap scenarios use the primary calendar policy to
isolate the assumption being changed and keep the experiment tractable.

Costs, training windows, position caps and market regimes answer different questions.
Inspect the evaluation dates before comparing numbers. Window scenarios use a common later
start; costs and caps use the baseline period. The same dated BIL series evaluates every
strategy, so an unchanged equal-weight path has the same Sharpe across window choices.

The eight-criterion scorecard and its limits are documented in [methodology](methodology.md).
Failures stay in the scenario tables with a reason. The dashboard leaves gaps rather than
joining a successful point across an unobserved result. Drawdown durations use calendar days;
open episodes have no recovery date. Concentration measures decision weights, not daily drift.
