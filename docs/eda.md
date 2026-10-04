# Exploratory Data Analysis Design

The EDA pipeline is a thin project client. It reads the governed processed price
matrix, restricts the analysis to the nine investable assets, and delegates all
financial calculations and figures to `portfolio-management-module`.

## Coverage

- Dataset overview and missing-value summary
- Adjusted-close and normalized-price analysis
- Simple daily returns and descriptive statistics
- Non-destructive IQR outlier flags
- Pearson correlation matrix and rolling VTI/IEF correlation
- 63-day annualized volatility and 252-day compounded return
- Full underwater drawdown paths and maximum-drawdown summaries
- Return distributions and interactive diagnostic figures

The initial outlier threshold is three interquartile ranges. Outlier flags are
diagnostic only: no observation is deleted, winsorized, or otherwise altered.
Daily return volatility is annualized with 252 periods. These configuration
choices are explicit in `configs/base.yaml` and may be changed without adding
logic to notebooks.

All interpretations are descriptive, sample-dependent, and not forecasts.
