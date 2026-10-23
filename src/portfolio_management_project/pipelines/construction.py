"""Static classical portfolio-construction orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from portfolio_management.data import MarketData
from portfolio_management.models import (
    CapitalAllocationLineResult,
    EfficientFrontierResult,
    OptimizationResult,
)
from portfolio_management.portfolio import Portfolio
from portfolio_management.visualization import (
    BaseFigure,
    EfficientFrontierFigure,
    RiskContributionFigure,
)

from portfolio_management_project.config import ResearchConfig
from portfolio_management_project.estimation import estimate_market
from portfolio_management_project.exceptions import DataPipelineError
from portfolio_management_project.inputs import read_prices

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConstructionResult:
    """Contain all static classical portfolio-construction outputs."""

    expected_returns: pd.Series
    covariance_matrix: pd.DataFrame
    risk_free_rate: float
    optimizations: dict[str, OptimizationResult]
    portfolios: dict[str, Portfolio]
    weights: pd.DataFrame
    ex_ante_summary: pd.DataFrame
    realized_summary: pd.DataFrame
    risk_contributions: pd.DataFrame
    frontier: EfficientFrontierResult
    capital_allocation_line: CapitalAllocationLineResult
    figures: dict[str, BaseFigure]


@dataclass(frozen=True)
class ConstructionExportResult:
    """Contain exported construction artifact locations."""

    tables_directory: Path
    figures_directory: Path
    summary_path: Path


def run_construction_pipeline(
    config: ResearchConfig,
    *,
    prices: pd.DataFrame | None = None,
    export: bool = True,
) -> tuple[ConstructionResult, ConstructionExportResult | None]:
    """Estimate inputs and run every currently supported classical model."""
    source = read_prices(config) if prices is None else prices.copy()
    missing_assets = [ticker for ticker in config.universe.tickers if ticker not in source]
    if missing_assets:
        raise DataPipelineError(f"Processed prices omit investable assets: {missing_assets}.")
    sample = source.loc[
        source.index >= pd.Timestamp(config.portfolio_construction.sample_start),
        config.universe.tickers,
    ].sort_index()
    periods = config.portfolio_construction.periods_per_year
    estimate = estimate_market(sample, config, minimum_observations=periods)
    expected_returns = estimate.expected_returns
    covariance = estimate.covariance
    risk_free_rate = estimate.cash_rate
    optimizer = estimate.optimizer
    optimizations = {
        "equal_weight": optimizer.equal_weight(),
        "minimum_variance": optimizer.minimum_variance(),
        "mean_variance": optimizer.mean_variance(
            risk_aversion=config.portfolio_construction.risk_aversion
        ),
        "target_return": optimizer.target_return(config.portfolio_construction.target_return),
        "maximum_sharpe": optimizer.maximum_sharpe(),
    }
    frontier = optimizer.efficient_frontier(
        n_portfolios=config.portfolio_construction.frontier_portfolios
    )
    allocation_line = optimizer.capital_allocation_line(
        n_points=config.portfolio_construction.frontier_portfolios
    )
    market_data = MarketData(
        prices=sample,
        provider="project_processed",
        price_field="adjusted_close",
        frequency="1d",
    )
    portfolios = {
        name: result.to_portfolio(
            market_data,
            periods_per_year=periods,
            risk_free_rate=risk_free_rate,
        )
        for name, result in optimizations.items()
    }
    weights = pd.DataFrame({name: result.weights for name, result in optimizations.items()})
    ex_ante_summary = pd.DataFrame(
        {name: result.summary() for name, result in optimizations.items()}
    ).T
    realized_summary = pd.DataFrame(
        {name: portfolio.summary() for name, portfolio in portfolios.items()}
    ).T
    risk_contributions = pd.concat(
        {
            name: portfolio.risk_attribution().percentage_contribution()
            for name, portfolio in portfolios.items()
        },
        axis=1,
    )
    figures: dict[str, BaseFigure] = {
        "efficient_frontier": EfficientFrontierFigure(
            frontier,
            highlighted_portfolios={
                name.replace("_", " ").title(): result for name, result in optimizations.items()
            },
            capital_allocation_line=allocation_line,
        ),
        "maximum_sharpe_risk_contribution": RiskContributionFigure(
            portfolios["maximum_sharpe"].risk_attribution()
        ),
    }
    result = ConstructionResult(
        expected_returns=expected_returns,
        covariance_matrix=covariance,
        risk_free_rate=risk_free_rate,
        optimizations=optimizations,
        portfolios=portfolios,
        weights=weights,
        ex_ante_summary=ex_ante_summary,
        realized_summary=realized_summary,
        risk_contributions=risk_contributions,
        frontier=frontier,
        capital_allocation_line=allocation_line,
        figures=figures,
    )
    exported = export_construction_result(config, result) if export else None
    return result, exported


def export_construction_result(
    config: ResearchConfig,
    result: ConstructionResult,
) -> ConstructionExportResult:
    """Export construction tables, figures, and methodological cautions."""
    root = config.paths.artifacts / "portfolio_construction"
    tables = root / "tables"
    figures = root / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    table_map = {
        "expected_returns": result.expected_returns.to_frame("expected_return"),
        "covariance_matrix": result.covariance_matrix,
        "weights": result.weights,
        "ex_ante_summary": result.ex_ante_summary,
        "realized_summary": result.realized_summary,
        "risk_contributions": result.risk_contributions,
        "efficient_frontier": pd.DataFrame(
            {
                "expected_return": result.frontier.expected_returns,
                "volatility": result.frontier.volatilities,
                "sharpe_ratio": result.frontier.sharpe_ratios,
            }
        ),
        "capital_allocation_line": pd.DataFrame(
            {
                "allocation": result.capital_allocation_line.allocations,
                "risk_free_allocation": result.capital_allocation_line.risk_free_allocations,
                "expected_return": result.capital_allocation_line.expected_returns,
                "volatility": result.capital_allocation_line.volatilities,
            }
        ),
    }
    for name, table in table_map.items():
        table.to_csv(tables / f"{name}.csv")
    for name, figure in result.figures.items():
        figure.save_html(figures / f"{name}.html")
    summary_path = root / "construction_summary.md"
    summary_path.write_text(
        "# Static Portfolio Construction\n\n"
        f"- Risk-free proxy: {config.portfolio_construction.risk_free_asset} "
        f"({result.risk_free_rate:.2%} historical annualized estimate).\n"
        f"- Common weight bounds: {config.portfolio_construction.min_weight:.0%} to "
        f"{config.portfolio_construction.max_weight:.0%}.\n"
        f"- Target return: {config.portfolio_construction.target_return:.2%}.\n"
        "- The five strategies use one full historical sample and are not out-of-sample "
        "backtest results.\n"
        "- Risk Parity, HRP, and Black-Litterman are excluded until tested library "
        "implementations are available.\n",
        encoding="utf-8",
    )
    LOGGER.info("Portfolio-construction artifacts exported to %s.", root)
    return ConstructionExportResult(tables, figures, summary_path)
