"""Build consistent model inputs through the core library's estimators."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from portfolio_management.analytics import calculate_returns
from portfolio_management.estimators import historical_mean_return, ledoit_wolf_covariance
from portfolio_management.models import PortfolioOptimizer

from portfolio_management_project.config import ResearchConfig


@dataclass(frozen=True)
class MarketEstimate:
    """The inputs and optimizer for one declared information window."""

    expected_returns: pd.Series
    covariance: pd.DataFrame
    cash_rate: float
    optimizer: PortfolioOptimizer


def estimate_market(
    prices: pd.DataFrame,
    config: ResearchConfig,
    *,
    minimum_observations: int,
) -> MarketEstimate:
    """Use the same estimation recipe for static examples and dated decisions."""
    returns = calculate_returns(prices, method="simple")
    if not isinstance(returns, pd.DataFrame):
        raise TypeError("Model prices must produce a return DataFrame.")
    settings = config.portfolio_construction
    means = historical_mean_return(
        returns,
        annualization_factor=settings.periods_per_year,
        min_periods=minimum_observations,
    )
    covariance = ledoit_wolf_covariance(
        returns,
        annualization_factor=settings.periods_per_year,
        min_periods=minimum_observations,
    )
    cash_rate = float(means[settings.risk_free_asset])
    optimizer = PortfolioOptimizer(
        means,
        covariance,
        risk_free_rate=cash_rate,
        min_weight=settings.min_weight,
        max_weight=settings.max_weight,
    )
    return MarketEstimate(means, covariance, cash_rate, optimizer)
