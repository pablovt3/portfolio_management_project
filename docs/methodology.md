# Research methodology

## Separate the question from the implementation

We ask whether optimized allocation improves the mix of growth, risk and trading effort
relative to a simple global policy. The universe, sample and constraints are explicit YAML
inputs. Validated settings stay in `config.py`; orchestration is in `research.py`; reusable
financial operations come from `portfolio-management-module`.

## Information and execution

Each portfolio model is paired with five execution policies. Two policies estimate and trade
on monthly or quarterly calendar dates. Three policies re-estimate targets monthly but trade
only when at least one pre-trade weight differs from its latest target by more than 2.5, 5 or
7.5 percentage points. A trigger restores the full target vector; it is not a partial trade to
the nearest boundary. The trigger is evaluated before the day's return, and every target is
estimated from a window ending before that date.

The band grid is an ex ante sensitivity design. It is not fitted to maximize the historical
scorecard. Narrow bands should generally track targets more closely; wide bands should
generally trade less. Realized turnover and net outcomes determine whether that expectation
held in this sample.

A decision uses a trailing price window ending on the previous trading day. The library
executes at the decision-day close; the new holdings earn the following returns. The baseline
uses 756 daily returns and monthly or quarterly decisions. Full-sample allocations are
illustrations only. Estimation windows and target adjustments are exported for inspection.

The target-return model requests 7% but clips that request to the feasible interval. This
keeps the policy explicit and executable; it does not guarantee a realized return. The audit
records the requested/effective target and the information date for each decision.

## Benchmark and cash

The external benchmark is quarterly 60% VT / 40% BND. Weights drift between rebalances.
Both strategies and benchmark pay the same proportional rate on gross traded notional;
initial establishment costs are excluded for both. A 35% ETF cap applies to optimized
portfolios, not the policy benchmark. Differences therefore reflect universe and constraints
as well as allocation choices.

BIL is a separate cash proxy. Realized Sharpe is `mean(r_strategy - r_BIL) * 252` divided by
the annualized sample standard deviation of those daily excess returns. Calendar alignment
is mandatory. The core library's information-ratio primitive supplies this calculation with
cash as the reference. The library's scalar-rate, CAGR-based backtest summary is not used
as the published Sharpe. Static optimization still uses a trailing historical BIL estimate;
future cash observations affect evaluation only, never allocation decisions.

## Robustness and ranking

Cost scenarios span 0–25 bps. Window scenarios span 252–1260 observations on a common later
calendar starting in 2013. Position caps span 20–50%. Historical regimes are descriptive,
not signals fitted to predict the future. An uncompleted scenario remains marked as a
failure; it is not zero performance. The optimizer can reject a maximum-Sharpe case when
its required positive excess-return condition is unavailable.

The scorecard averages eight within-strategy ranks: CAGR, volatility, realized Sharpe,
maximum drawdown, Calmar, turnover, information ratio and average largest position.
Round inputs to ten decimals before ranking. Lower average rank is better. Metrics overlap,
so the score is a transparent descriptive preference—not an objective utility function.

## Interpretation limits

ETF selection is not survivorship-free or fully point-in-time. Results are USD denominated.
Taxes, market impact, changing spreads, investor liabilities and FX hedging are excluded.
Choosing the best model after seeing this sample is not an independent test of model
selection. Use a held-out evaluation or prospective paper portfolio for that next question.
