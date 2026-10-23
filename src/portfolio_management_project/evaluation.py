"""Evaluate this study against a dated cash series using the core library.

The library's backtest summary reports an ex-ante-style ratio with a scalar
cash rate. Our research question needs realized daily excess returns instead.
Keep that reporting convention here, without changing the trading engine.
"""

from __future__ import annotations

import pandas as pd
from portfolio_management.risk import information_ratio


def realized_sharpe(returns: pd.Series, cash: pd.Series, periods: int = 252) -> float:
    """Annualize mean daily excess return divided by its sample deviation.

    BIL is an investable cash proxy, not a guaranteed risk-free instrument.
    The library information-ratio primitive gives the same calculation when
    the reference series is cash. Missing cash observations are an error.
    """
    aligned_cash = cash.reindex(returns.index)
    if aligned_cash.isna().any():
        raise ValueError("Cash returns must cover every evaluation date.")
    if float((returns - aligned_cash).std()) <= 1e-14:
        return float("nan")
    return float(information_ratio(returns, aligned_cash, periods_per_year=periods))
