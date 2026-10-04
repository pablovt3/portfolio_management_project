# Static Portfolio Construction

The primary construction specification uses daily observations from 2011
through 2025, historical arithmetic mean returns, Ledoit-Wolf covariance,
and the historical annualized BIL return as the risk-free proxy.

Every model currently available through the library facade is evaluated under
common long-only 0%–35% asset bounds:

- Equal Weight
- Global Minimum Variance
- Mean-Variance with risk aversion 4
- Minimum Variance for a 7% target return
- Maximum Sharpe
- Efficient Frontier and Capital Allocation Line

The outputs also include realized constant-weight portfolio summaries and Euler
percentage risk contributions. Full-sample optimized weights are never labeled
as out-of-sample performance. Risk Parity, Hierarchical Risk Parity, and
Black-Litterman remain deferred until they exist as independently tested,
backward-compatible library models.
