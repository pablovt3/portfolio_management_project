"""Evaluate this study against a dated cash series using the core library.

The library's backtest summary reports an ex-ante-style ratio with a scalar
cash rate. Our research question needs realized daily excess returns instead.
Keep that reporting convention here, without changing the trading engine.
"""

from __future__ import annotations

import pandas as pd
from portfolio_management.risk import (
    historical_expected_shortfall,
    historical_var,
    information_ratio,
    parametric_expected_shortfall,
    parametric_var,
)


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


def tail_risk_metrics(
    returns: pd.Series,
    confidence_level: float = 0.95,
) -> pd.Series:
    """Return one-period historical and Gaussian tail-risk estimates.

    Parameters
    ----------
    returns : pandas.Series
        Net realized arithmetic returns expressed in decimal units.
    confidence_level : float, default 0.95
        Probability level used by every VaR and Expected Shortfall estimate.

    Returns
    -------
    pandas.Series
        VaR and Expected Shortfall as non-negative return-loss magnitudes.

    Notes
    -----
    The estimates use a one-observation horizon and are not annualized. Expected
    Shortfall is also known as Conditional Value at Risk (CVaR).
    """
    return pd.Series(
        {
            "historical_var": historical_var(
                returns,
                confidence_level=confidence_level,
            ),
            "historical_expected_shortfall": historical_expected_shortfall(
                returns,
                confidence_level=confidence_level,
            ),
            "parametric_var": parametric_var(
                returns,
                confidence_level=confidence_level,
            ),
            "parametric_expected_shortfall": parametric_expected_shortfall(
                returns,
                confidence_level=confidence_level,
            ),
        },
        name=returns.name,
        dtype=float,
    )
