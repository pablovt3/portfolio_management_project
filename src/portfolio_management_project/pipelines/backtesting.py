"""Out-of-sample walk-forward portfolio backtesting orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
from portfolio_management.analytics import calculate_returns
from portfolio_management.backtesting import (
    BacktestResult,
    CalendarRebalanceBacktest,
    ProportionalTransactionCost,
    RebalanceFrequency,
    StrategyComparison,
    ThresholdTrigger,
    WalkForwardBacktest,
)
from portfolio_management.data import MarketData
from portfolio_management.estimators import historical_mean_return
from portfolio_management.optimization import feasible_return_range
from portfolio_management.portfolio import Portfolio
from portfolio_management.visualization import (
    BacktestWeightEvolutionFigure,
    BaseFigure,
    StrategyDrawdownComparisonFigure,
    StrategyMetricComparisonFigure,
    StrategyWealthComparisonFigure,
)

from portfolio_management_project.config import ResearchConfig
from portfolio_management_project.estimation import estimate_market
from portfolio_management_project.evaluation import realized_sharpe
from portfolio_management_project.exceptions import DataPipelineError
from portfolio_management_project.inputs import read_prices

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestingResult:
    """Contain dynamic strategies, benchmark, comparison tables, and figures."""

    strategies: dict[str, BacktestResult]
    benchmark: BacktestResult
    comparison: StrategyComparison
    risk_free_rate: float
    figures: dict[str, BaseFigure]
    cash_returns: pd.Series
    allocation_audit: pd.DataFrame

    def summary(self) -> pd.DataFrame:
        """Use the same dated cash reference for every realized Sharpe."""
        table = self.comparison.summary()
        for name, result in self.comparison.strategies.items():
            table.loc[name, "sharpe_ratio"] = realized_sharpe(
                result.returns,
                self.cash_returns,
                result.periods_per_year,
            )
        return table.drop(columns="risk_free_rate", errors="ignore")

    def performance(self) -> pd.DataFrame:
        """Return comparable net performance for publication."""
        columns = self.comparison.performance_summary().columns
        return self.summary().loc[:, columns]


@dataclass(frozen=True)
class BacktestingExportResult:
    """Contain exported backtesting artifact locations."""

    tables_directory: Path
    figures_directory: Path
    summary_path: Path


def run_backtesting_pipeline(
    config: ResearchConfig,
    *,
    prices: pd.DataFrame | None = None,
    export: bool = True,
) -> tuple[BacktestingResult, BacktestingExportResult | None]:
    """Run calendar and drift-band policies with strictly lagged estimates."""
    source = read_prices(config) if prices is None else prices.copy()
    source = _validate_source_prices(config, source)
    universe_prices = source.loc[:, config.universe.tickers]
    evaluation_start = _evaluation_start(config, universe_prices)
    risk_free_rate = _initial_risk_free_rate(config, universe_prices, evaluation_start)
    benchmark = _run_benchmark(config, source, evaluation_start, risk_free_rate)
    transaction_cost = ProportionalTransactionCost(
        config.backtesting.transaction_cost_bps / 10_000.0
    )

    strategies: dict[str, BacktestResult] = {}
    audit: list[dict[str, object]] = []
    for strategy in config.backtesting.strategies:
        for frequency_name in config.backtesting.rebalance_frequencies:
            frequency = cast(RebalanceFrequency, frequency_name)
            label = f"{strategy}_{frequency}"
            estimator = _weight_estimator(config, strategy, audit=audit, label=label)
            LOGGER.info("Running walk-forward strategy %s.", label)
            strategies[label] = WalkForwardBacktest(
                prices=universe_prices,
                weight_estimator=estimator,
                lookback_periods=config.backtesting.lookback_periods,
                start_date=evaluation_start,
                frequency=frequency,
                periods_per_year=config.portfolio_construction.periods_per_year,
                risk_free_rate=risk_free_rate,
                initial_value=config.backtesting.initial_value,
                benchmark_returns=benchmark.returns,
                transaction_cost=transaction_cost,
            ).run()

        for threshold in config.backtesting.band_thresholds:
            frequency = cast(
                RebalanceFrequency,
                config.backtesting.band_estimation_frequency,
            )
            label = band_strategy_label(strategy, threshold)
            estimator = _weight_estimator(config, strategy, audit=audit, label=label)
            LOGGER.info("Running drift-band strategy %s.", label)
            strategies[label] = WalkForwardBacktest(
                prices=universe_prices,
                weight_estimator=estimator,
                lookback_periods=config.backtesting.lookback_periods,
                start_date=evaluation_start,
                frequency=frequency,
                periods_per_year=config.portfolio_construction.periods_per_year,
                risk_free_rate=risk_free_rate,
                initial_value=config.backtesting.initial_value,
                benchmark_returns=benchmark.returns,
                transaction_cost=transaction_cost,
                rebalance_trigger=ThresholdTrigger(threshold),
            ).run()

    comparison = StrategyComparison({**strategies, "benchmark_60_40": benchmark})
    representative_name = (
        "maximum_sharpe_monthly"
        if "maximum_sharpe_monthly" in strategies
        else next(iter(strategies))
    )
    figures: dict[str, BaseFigure] = {
        "strategy_wealth": StrategyWealthComparisonFigure(comparison),
        "strategy_drawdowns": StrategyDrawdownComparisonFigure(comparison),
        "strategy_metrics": StrategyMetricComparisonFigure(comparison),
        "representative_weights": BacktestWeightEvolutionFigure(
            strategies[representative_name],
            title=f"Weight Evolution: {representative_name.replace('_', ' ').title()}",
        ),
    }
    cash_returns = calculate_returns(
        source[[config.portfolio_construction.risk_free_asset]],
        method="simple",
    ).iloc[:, 0]
    result = BacktestingResult(
        strategies=strategies,
        benchmark=benchmark,
        comparison=comparison,
        risk_free_rate=risk_free_rate,
        figures=figures,
        cash_returns=cash_returns,
        allocation_audit=pd.DataFrame(audit),
    )
    exported = export_backtesting_result(config, result) if export else None
    return result, exported


def export_backtesting_result(
    config: ResearchConfig,
    result: BacktestingResult,
) -> BacktestingExportResult:
    """Export comparison, audit, allocation, and visualization artifacts."""
    root = config.paths.artifacts / "backtesting"
    tables = root / "tables"
    figures = root / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    result.summary().to_csv(tables / "strategy_summary.csv")
    result.performance().to_csv(tables / "strategy_performance.csv")
    result.comparison.trading_summary().to_csv(tables / "strategy_trading.csv")
    result.comparison.benchmark_summary().to_csv(tables / "strategy_benchmark_metrics.csv")
    result.comparison.returns().to_csv(tables / "strategy_returns.csv")
    result.comparison.normalized_wealth().to_csv(tables / "strategy_normalized_wealth.csv")
    result.comparison.drawdowns().to_csv(tables / "strategy_drawdowns.csv")
    _decision_weights(result.strategies).to_csv(tables / "decision_weights.csv")
    _estimation_windows(result.strategies).to_csv(tables / "estimation_windows.csv")
    result.allocation_audit.to_csv(tables / "allocation_audit.csv", index=False)
    result.benchmark.weights_history.to_csv(tables / "benchmark_weights.csv")
    result.benchmark.events().to_csv(tables / "benchmark_rebalance_events.csv")
    for name, figure in result.figures.items():
        figure.save_html(figures / f"{name}.html")

    performance = result.performance()
    strategy_performance = performance.loc[list(result.strategies)]
    sharpe = pd.to_numeric(strategy_performance["sharpe_ratio"], errors="coerce")
    best_sharpe = str(sharpe.idxmax())
    annualized_returns = pd.to_numeric(strategy_performance["annualized_return"], errors="coerce")
    best_return = str(annualized_returns.idxmax())
    summary_path = root / "backtesting_summary.md"
    summary_path.write_text(
        "# Walk-Forward Backtesting\n\n"
        f"- Out-of-sample start: {result.benchmark.wealth.index[0].date()}.\n"
        f"- Trailing estimation window: {config.backtesting.lookback_periods} returns.\n"
        f"- Rebalancing frequencies: {', '.join(config.backtesting.rebalance_frequencies)}.\n"
        f"- Drift bands: {_format_band_thresholds(config.backtesting.band_thresholds)}; "
        f"targets are re-estimated {config.backtesting.band_estimation_frequency}.\n"
        f"- Transaction cost: {config.backtesting.transaction_cost_bps:.1f} basis points "
        "on gross traded notional.\n"
        f"- External benchmark: {config.benchmark.name}, rebalanced "
        f"{config.benchmark.rebalance_frequency}.\n"
        f"- Highest realized Sharpe ratio: {best_sharpe} ({sharpe[best_sharpe]:.3f}).\n"
        f"- Highest realized annualized return: {best_return} "
        f"({annualized_returns[best_return]:.2%}).\n"
        "- Every allocation uses a trailing window ending before its decision date; "
        "the exported estimation-window table is the audit trail.\n"
        "- The investable set remains fixed through time, but ETF selection was made "
        "with present-day availability and therefore does not constitute a fully "
        "point-in-time survivorship-free universe.\n",
        encoding="utf-8",
    )
    LOGGER.info("Backtesting artifacts exported to %s.", root)
    return BacktestingExportResult(tables, figures, summary_path)


def _weight_estimator(
    config: ResearchConfig,
    strategy: str,
    *,
    audit: list[dict[str, object]] | None = None,
    label: str = "",
) -> Callable[[pd.DataFrame], pd.Series]:
    """Build a project-specific model adapter backed by library estimators."""

    def estimate(training_prices: pd.DataFrame) -> pd.Series:
        estimate = estimate_market(
            training_prices,
            config,
            minimum_observations=config.backtesting.lookback_periods,
        )
        expected_returns = estimate.expected_returns
        optimizer = estimate.optimizer
        if strategy == "equal_weight":
            return optimizer.equal_weight().weights
        if strategy == "minimum_variance":
            return optimizer.minimum_variance().weights
        if strategy == "mean_variance":
            return optimizer.mean_variance(
                risk_aversion=config.portfolio_construction.risk_aversion
            ).weights
        if strategy == "target_return":
            lower, upper = feasible_return_range(
                expected_returns.to_numpy(dtype=float),
                lower_bound=config.portfolio_construction.min_weight,
                upper_bound=config.portfolio_construction.max_weight,
            )
            target = float(np.clip(config.portfolio_construction.target_return, lower, upper))
            if audit is not None:
                audit.append(
                    {
                        "strategy": label,
                        "information_date": training_prices.index[-1],
                        "requested_target": config.portfolio_construction.target_return,
                        "effective_target": target,
                        "target_adjusted": abs(target - config.portfolio_construction.target_return)
                        > 1e-10,
                        "feasible_minimum": lower,
                        "feasible_maximum": upper,
                    }
                )
            return optimizer.target_return(target).weights
        if strategy == "maximum_sharpe":
            return optimizer.maximum_sharpe().weights
        raise ValueError(f"Unsupported walk-forward strategy: {strategy}.")

    return estimate


def _run_benchmark(
    config: ResearchConfig,
    source: pd.DataFrame,
    evaluation_start: pd.Timestamp,
    risk_free_rate: float,
) -> BacktestResult:
    prices = source.loc[
        source.index >= evaluation_start,
        config.benchmark.tickers,
    ]
    if prices.isna().any().any():
        raise DataPipelineError("Benchmark prices contain missing out-of-sample values.")
    market_data = MarketData(
        prices=prices,
        provider="project_processed",
        price_field="adjusted_close",
        frequency="1d",
    )
    weights = pd.Series(
        {item.ticker: item.weight for item in config.benchmark.constituents},
        dtype=float,
    )
    portfolio = Portfolio(
        weights=weights,
        market_data=market_data,
        periods_per_year=config.portfolio_construction.periods_per_year,
        risk_free_rate=risk_free_rate,
    )
    return CalendarRebalanceBacktest(
        portfolio,
        frequency=cast(RebalanceFrequency, config.benchmark.rebalance_frequency),
        initial_value=config.backtesting.initial_value,
        transaction_cost=ProportionalTransactionCost(
            config.backtesting.transaction_cost_bps / 10_000.0,
        ),
    ).run()


def _evaluation_start(
    config: ResearchConfig,
    prices: pd.DataFrame,
) -> pd.Timestamp:
    candidates = prices.index[prices.index >= pd.Timestamp(config.study.out_of_sample_start)]
    if candidates.empty:
        raise DataPipelineError("No prices exist on or after the out-of-sample start.")
    return pd.Timestamp(candidates[0])


def _initial_risk_free_rate(
    config: ResearchConfig,
    prices: pd.DataFrame,
    evaluation_start: pd.Timestamp,
) -> float:
    position = int(prices.index.get_loc(evaluation_start))
    start = position - config.backtesting.lookback_periods - 1
    if start < 0:
        raise DataPipelineError("Insufficient history for the configured lookback window.")
    training_prices = prices.iloc[start:position]
    returns = calculate_returns(training_prices, method="simple")
    if not isinstance(returns, pd.DataFrame):
        raise TypeError("Training prices must produce a return DataFrame.")
    estimates = historical_mean_return(
        returns,
        annualization_factor=config.portfolio_construction.periods_per_year,
        min_periods=config.backtesting.lookback_periods,
    )
    return float(estimates[config.portfolio_construction.risk_free_asset])


def _decision_weights(strategies: dict[str, BacktestResult]) -> pd.DataFrame:
    frames: dict[str, pd.DataFrame] = {}
    for name, result in strategies.items():
        if result.estimation_windows is None:
            raise ValueError("Walk-forward results require weights and estimation windows.")
        weights = (
            result.target_weights_history
            if result.target_weights_history is not None
            else result.weights_history
        )
        if weights is None:
            raise ValueError("Walk-forward results require target weights.")
        frames[name] = weights.loc[result.estimation_windows.index]
    return pd.concat(frames, names=["strategy", "decision_date"])


def band_strategy_label(strategy: str, threshold: float) -> str:
    """Build a stable identifier whose suffix states the absolute band in points."""
    basis_points = round(threshold * 10_000)
    if not np.isclose(threshold * 10_000, basis_points):
        raise ValueError("Band thresholds must resolve to a whole basis point.")
    return f"{strategy}_band_{basis_points}bp"


def _format_band_thresholds(thresholds: tuple[float, ...]) -> str:
    if not thresholds:
        return "none"
    return ", ".join(f"±{threshold:.1%}" for threshold in thresholds)


def _estimation_windows(strategies: dict[str, BacktestResult]) -> pd.DataFrame:
    frames = {
        name: result.estimation_windows
        for name, result in strategies.items()
        if result.estimation_windows is not None
    }
    if len(frames) != len(strategies):
        raise ValueError("Every walk-forward result requires estimation-window records.")
    return pd.concat(frames, names=["strategy", "decision_date"])


def _validate_source_prices(
    config: ResearchConfig,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    missing_assets = [ticker for ticker in config.requested_tickers if ticker not in prices]
    if missing_assets:
        raise DataPipelineError(f"Processed prices omit required assets: {missing_assets}.")
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise TypeError("Processed prices must use a DatetimeIndex.")
    result = prices.loc[:, config.requested_tickers].sort_index().astype(float)
    if result.loc[:, config.universe.tickers].isna().any().any():
        raise DataPipelineError("Investable prices contain missing values.")
    if (result.dropna() <= 0.0).any().any():
        raise DataPipelineError("Processed prices must be strictly positive.")
    return result
