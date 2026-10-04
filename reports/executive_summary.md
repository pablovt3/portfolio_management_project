# Global multi-asset research — executive note

Evaluation: 2011-01-03 to 2025-12-31.

Does optimized allocation improve the balance of growth, risk and trading effort relative to a simple global policy? We compare five rules under calendar schedules and three drift-band policies.

- Target Return Band 500Bp leads the declared eight-criterion scorecard.
- Target Return Band 750Bp has the highest observed CAGR (7.39%).
- Target Return Band 750Bp has the highest realized cash-reference Sharpe (0.888).
- Minimum Variance Band 750Bp has the smallest maximum drawdown (11.60%).
- The scorecard leader's CAGR differs from the net benchmark by +0.20 percentage points per year.
- Incomplete window scenarios: 1; inspect their recorded reasons before drawing a robustness conclusion.

## Benchmark and measurement

The reference is 60% VT / 40% BND, rebalanced quarterly. Both sides pay the same 10 bps on gross rebalance notional. Initial purchase costs are excluded for both. BIL is a separate dated cash reference for Sharpe.

Realized Sharpe uses the mean and sample deviation of daily excess returns over BIL, annualized at 252 observations. CAGR remains compound growth.

## Decision framework

The scorecard averages eight ranks: CAGR, volatility, Sharpe, drawdown, Calmar, turnover, information ratio and average largest position. Several criteria overlap. The ranking is a declared preference, not a universal investor utility function.

## Compact strategy snapshot

| Strategy | Annualized return (CAGR) | Annualized volatility | Sharpe vs cash | Maximum drawdown |
| --- | --- | --- | --- | --- |
| Target return · drift band ±5 pp | 7.39% | 6.83% | 0.885 | 16.29% |
| Equal weight · quarterly | 5.94% | 8.31% | 0.577 | 19.68% |
| Global 60/40 | 7.18% | 10.41% | 0.592 | 22.33% |

## Robustness and next step

The window experiment shares a later calendar to accommodate its longest training period. Costs and position caps use the baseline calendar. Incomplete scenarios stay visible in the evidence rather than becoming zero returns.

The sample is also used to identify the leaders. A separate holdout or a prospective paper portfolio is needed to test a selection rule. The universe is not fully point-in-time; taxes, market impact, variable spreads, liabilities and FX hedging remain outside this study.
