"""Study-specific robustness and portfolio-diagnostic orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

import pandas as pd
from portfolio_management.analytics import annualized_return
from portfolio_management.backtesting import BacktestResult
from portfolio_management.risk import (
    annualized_volatility,
    maximum_drawdown,
)

from portfolio_management_project.config import (
    RegimeSettings,
    ResearchConfig,
)
from portfolio_management_project.evaluation import realized_sharpe
from portfolio_management_project.exceptions import DataPipelineError
from portfolio_management_project.inputs import read_prices
from portfolio_management_project.pipelines.backtesting import (
    BacktestingResult,
    run_backtesting_pipeline,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RobustnessResult:
    """Contain robustness scenarios and diagnostic study tables."""

    drawdown_episodes: pd.DataFrame
    drawdown_summary: pd.DataFrame
    concentration_summary: pd.DataFrame
    regime_performance: pd.DataFrame
    cost_sensitivity: pd.DataFrame
    lookback_sensitivity: pd.DataFrame
    weight_cap_sensitivity: pd.DataFrame
    scorecard: pd.DataFrame


@dataclass(frozen=True)
class RobustnessExportResult:
    """Contain exported robustness artifact locations."""

    tables_directory: Path
    summary_path: Path


def run_robustness_pipeline(
    config: ResearchConfig,
    *,
    prices: pd.DataFrame | None = None,
    baseline: BacktestingResult | None = None,
    export: bool = True,
) -> tuple[RobustnessResult, RobustnessExportResult | None]:
    """Run diagnostic and sensitivity analyses around the baseline experiment."""
    source = read_prices(config) if prices is None else prices.copy()
    baseline_result = (
        run_backtesting_pipeline(config, prices=source, export=False)[0]
        if baseline is None
        else baseline
    )
    all_results = {
        **baseline_result.strategies,
        "benchmark_60_40": baseline_result.benchmark,
    }
    episodes = pd.concat(
        {
            name: _drawdown_episodes(
                result,
                limit=config.robustness.drawdown_episodes,
            )
            for name, result in all_results.items()
        },
        names=["strategy", "episode"],
    )
    drawdown_summary = _drawdown_summary(episodes)
    concentration = _concentration_summary(baseline_result.strategies)
    regime_performance = _regime_performance(config, all_results, baseline_result.cash_returns)
    cost_sensitivity = _cost_sensitivity(config, source, baseline_result)
    lookback_sensitivity = _lookback_sensitivity(config, source)
    weight_cap_sensitivity = _weight_cap_sensitivity(config, source)
    scorecard = _build_scorecard(baseline_result, concentration)
    result = RobustnessResult(
        drawdown_episodes=episodes,
        drawdown_summary=drawdown_summary,
        concentration_summary=concentration,
        regime_performance=regime_performance,
        cost_sensitivity=cost_sensitivity,
        lookback_sensitivity=lookback_sensitivity,
        weight_cap_sensitivity=weight_cap_sensitivity,
        scorecard=scorecard,
    )
    exported = export_robustness_result(config, result) if export else None
    return result, exported


def export_robustness_result(
    config: ResearchConfig,
    result: RobustnessResult,
) -> RobustnessExportResult:
    """Export robustness tables and a concise methodological summary."""
    root = config.paths.artifacts / "robustness"
    tables = root / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    table_map = {
        "drawdown_episodes": result.drawdown_episodes,
        "drawdown_summary": result.drawdown_summary,
        "concentration_summary": result.concentration_summary,
        "regime_performance": result.regime_performance,
        "cost_sensitivity": result.cost_sensitivity,
        "lookback_sensitivity": result.lookback_sensitivity,
        "weight_cap_sensitivity": result.weight_cap_sensitivity,
        "strategy_scorecard": result.scorecard,
    }
    for name, table in table_map.items():
        table.to_csv(tables / f"{name}.csv", date_format="%Y-%m-%d")

    leader = str(result.scorecard.index[0])
    summary_path = root / "robustness_summary.md"
    summary_path.write_text(
        "# Robustness and Diagnostic Analysis\n\n"
        f"- Balanced scorecard leader: {leader}.\n"
        f"- Transaction-cost scenarios: {config.robustness.cost_scenarios_bps} bps.\n"
        f"- Lookback scenarios: {config.robustness.lookback_scenarios} returns.\n"
        f"- Maximum-weight scenarios: {config.robustness.max_weight_scenarios}.\n"
        f"- Historical regimes: {len(config.robustness.regimes)}.\n"
        "- The scorecard is an equal-weighted research diagnostic, not a universal "
        "investor utility function.\n",
        encoding="utf-8",
    )
    LOGGER.info("Robustness artifacts exported to %s.", root)
    return RobustnessExportResult(tables, summary_path)


def _drawdown_episodes(
    result: BacktestResult,
    *,
    limit: int,
) -> pd.DataFrame:
    """Extract the deepest peak-to-recovery episodes from one result."""
    drawdowns = result.drawdowns
    episodes: list[dict[str, object]] = []
    start_position: int | None = None
    for position, value in enumerate(drawdowns.to_numpy(dtype=float)):
        if value < -1e-12 and start_position is None:
            start_position = max(position - 1, 0)
        recovered = value >= -1e-12 and start_position is not None
        if recovered:
            assert start_position is not None
            episodes.append(_episode_record(drawdowns, start_position, position))
            start_position = None
    if start_position is not None:
        episodes.append(
            _episode_record(drawdowns, start_position, len(drawdowns) - 1, open_episode=True)
        )
    if not episodes:
        return pd.DataFrame(
            columns=[
                "peak_date",
                "trough_date",
                "recovery_date",
                "depth",
                "duration_days",
                "recovery_days",
                "recovered",
            ]
        )
    frame = pd.DataFrame(episodes).sort_values("depth", ascending=False).head(limit)
    frame.index = pd.RangeIndex(1, len(frame) + 1, name="episode")
    return frame


def _episode_record(
    drawdowns: pd.Series,
    start_position: int,
    end_position: int,
    *,
    open_episode: bool = False,
) -> dict[str, object]:
    segment = drawdowns.iloc[start_position : end_position + 1]
    peak_date = pd.Timestamp(segment.index[0])
    trough_date = pd.Timestamp(segment.idxmin())
    recovery_date = pd.NaT if open_episode else pd.Timestamp(segment.index[-1])
    end_date = pd.Timestamp(segment.index[-1])
    return {
        "peak_date": peak_date,
        "trough_date": trough_date,
        "recovery_date": recovery_date,
        "depth": -float(segment.min()),
        "duration_days": int((end_date - peak_date).days),
        "recovery_days": (pd.NA if open_episode else int((recovery_date - trough_date).days)),
        "recovered": not open_episode,
    }


def _drawdown_summary(episodes: pd.DataFrame) -> pd.DataFrame:
    if episodes.empty:
        return pd.DataFrame()
    first = episodes.groupby(level="strategy", sort=False).head(1).droplevel("episode")
    first.index.name = "strategy"
    return first


def _concentration_summary(
    strategies: dict[str, BacktestResult],
) -> pd.DataFrame:
    rows: dict[str, dict[str, float]] = {}
    for name, result in strategies.items():
        if result.weights_history is None or result.estimation_windows is None:
            raise ValueError("Dynamic strategies require decision-weight histories.")
        weights = result.weights_history.loc[result.estimation_windows.index]
        hhi = weights.pow(2).sum(axis=1)
        max_weight = weights.max(axis=1)
        allocation_change = 0.5 * weights.diff().abs().sum(axis=1)
        rows[name] = {
            "average_max_weight": float(max_weight.mean()),
            "maximum_observed_weight": float(max_weight.max()),
            "average_effective_assets": float((1.0 / hhi).mean()),
            "minimum_effective_assets": float((1.0 / hhi).min()),
            "average_decision_weight_change": float(allocation_change.dropna().mean()),
        }
    frame = pd.DataFrame.from_dict(rows, orient="index")
    frame.index.name = "strategy"
    return frame


def _regime_performance(
    config: ResearchConfig,
    results: dict[str, BacktestResult],
    cash_returns: pd.Series,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    periods = config.portfolio_construction.periods_per_year
    for regime in config.robustness.regimes:
        for name, result in results.items():
            returns = result.returns.loc[
                (result.returns.index >= pd.Timestamp(regime.start_date))
                & (result.returns.index <= pd.Timestamp(regime.end_date))
            ]
            if returns.empty:
                continue
            realized_return = annualized_return(
                returns,
                periods_per_year=periods,
                method="simple",
            )
            if not isinstance(realized_return, float):
                raise TypeError("Regime annualized return must be a float.")
            volatility = annualized_volatility(returns, periods_per_year=periods)
            rows.append(
                {
                    "regime": regime.name,
                    "regime_label": regime.label,
                    "strategy": name,
                    "start_date": returns.index.min(),
                    "end_date": returns.index.max(),
                    "observations": len(returns),
                    "annualized_return": realized_return,
                    "annualized_volatility": volatility,
                    "sharpe_ratio": (
                        realized_sharpe(returns, cash_returns, periods)
                        if volatility > 0.0
                        else float("nan")
                    ),
                    "maximum_drawdown": maximum_drawdown(returns),
                }
            )
    return pd.DataFrame(rows).set_index(["regime", "strategy"])


def _cost_sensitivity(
    config: ResearchConfig,
    prices: pd.DataFrame,
    baseline: BacktestingResult,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for cost_bps in config.robustness.cost_scenarios_bps:
        if cost_bps == config.backtesting.transaction_cost_bps:
            scenario = baseline
        else:
            scenario_config = replace(
                config,
                backtesting=replace(
                    config.backtesting,
                    transaction_cost_bps=cost_bps,
                ),
            )
            scenario = run_backtesting_pipeline(
                scenario_config,
                prices=prices,
                export=False,
            )[0]
        summary = scenario.summary().loc[list(scenario.strategies)].copy()
        summary.insert(0, "cost_bps", cost_bps)
        summary.insert(1, "strategy", summary.index)
        frames.append(summary.reset_index(drop=True))
    return pd.concat(frames, ignore_index=True).set_index(["cost_bps", "strategy"])


def _lookback_sensitivity(
    config: ResearchConfig,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    common_date = _common_sensitivity_start(config, prices)
    sensitivity_regime = RegimeSettings(
        name="sensitivity_period",
        label="Common Sensitivity Period",
        start_date=common_date.date(),
        end_date=config.study.end_date - timedelta(days=1),
    )
    rows: list[dict[str, object]] = []
    for lookback in config.robustness.lookback_scenarios:
        for strategy in config.backtesting.strategies:
            scenario_config = replace(
                config,
                study=replace(config.study, out_of_sample_start=common_date.date()),
                backtesting=replace(
                    config.backtesting,
                    lookback_periods=lookback,
                    rebalance_frequencies=(config.robustness.primary_frequency,),
                    strategies=(strategy,),
                    band_thresholds=(),
                ),
                robustness=replace(config.robustness, regimes=(sensitivity_regime,)),
            )
            rows.append(
                _run_sensitivity_case(
                    scenario_config,
                    prices,
                    scenario_name="lookback_periods",
                    scenario_value=lookback,
                    strategy=strategy,
                )
            )
    return pd.DataFrame(rows).set_index(["lookback_periods", "strategy"])


def _weight_cap_sensitivity(
    config: ResearchConfig,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    optimized = tuple(
        strategy for strategy in config.backtesting.strategies if strategy != "equal_weight"
    )
    rows: list[dict[str, object]] = []
    for maximum_weight in config.robustness.max_weight_scenarios:
        for strategy in optimized:
            scenario_config = replace(
                config,
                portfolio_construction=replace(
                    config.portfolio_construction,
                    max_weight=maximum_weight,
                ),
                backtesting=replace(
                    config.backtesting,
                    strategies=(strategy,),
                    rebalance_frequencies=(config.robustness.primary_frequency,),
                    band_thresholds=(),
                ),
            )
            rows.append(
                _run_sensitivity_case(
                    scenario_config,
                    prices,
                    scenario_name="max_weight",
                    scenario_value=maximum_weight,
                    strategy=strategy,
                )
            )
    return pd.DataFrame(rows).set_index(["max_weight", "strategy"])


def _run_sensitivity_case(
    config: ResearchConfig,
    prices: pd.DataFrame,
    *,
    scenario_name: str,
    scenario_value: int | float,
    strategy: str,
) -> dict[str, object]:
    """Run one isolated case and preserve mathematically infeasible outcomes."""
    label = f"{strategy}_{config.robustness.primary_frequency}"
    row: dict[str, object] = {
        scenario_name: scenario_value,
        "strategy": label,
        "status": "success",
        "error": "",
    }
    try:
        scenario = run_backtesting_pipeline(
            config,
            prices=prices,
            export=False,
        )[0]
    except (ValueError, RuntimeError) as error:
        row["status"] = "infeasible"
        row["error"] = str(error)
        return row
    row.update(scenario.summary().loc[label].to_dict())
    return row


def _common_sensitivity_start(
    config: ResearchConfig,
    prices: pd.DataFrame,
) -> pd.Timestamp:
    universe = prices.loc[:, config.universe.tickers].dropna(how="any")
    required_position = max(config.robustness.lookback_scenarios) + 1
    if len(universe) <= required_position + 1:
        raise DataPipelineError("Insufficient history for robustness lookback scenarios.")
    history_date = pd.Timestamp(universe.index[required_position])
    return max(history_date, pd.Timestamp(config.study.out_of_sample_start))


def _build_scorecard(
    baseline: BacktestingResult,
    concentration: pd.DataFrame,
) -> pd.DataFrame:
    names = list(baseline.strategies)
    performance = baseline.performance().loc[names]
    trading = baseline.comparison.trading_summary().loc[names]
    relative = baseline.comparison.benchmark_summary().loc[names]
    metrics = pd.DataFrame(index=names)
    metrics["annualized_return"] = pd.to_numeric(performance["annualized_return"])
    metrics["annualized_volatility"] = pd.to_numeric(performance["annualized_volatility"])
    metrics["sharpe_ratio"] = pd.to_numeric(performance["sharpe_ratio"])
    metrics["maximum_drawdown"] = pd.to_numeric(performance["maximum_drawdown"])
    metrics["calmar_ratio"] = pd.to_numeric(performance["calmar_ratio"])
    metrics["total_turnover"] = pd.to_numeric(trading["total_turnover"])
    metrics["information_ratio"] = pd.to_numeric(relative["information_ratio"])
    metrics["average_max_weight"] = concentration.loc[names, "average_max_weight"]
    directions = {
        "annualized_return": False,
        "annualized_volatility": True,
        "sharpe_ratio": False,
        "maximum_drawdown": True,
        "calmar_ratio": False,
        "total_turnover": True,
        "information_ratio": False,
        "average_max_weight": True,
    }
    ranks = pd.DataFrame(
        {
            f"{metric}_rank": metrics[metric]
            .round(10)
            .rank(
                ascending=ascending,
                method="average",
            )
            for metric, ascending in directions.items()
        }
    )
    scorecard = pd.concat([metrics, ranks], axis=1)
    scorecard["balanced_rank_score"] = ranks.mean(axis=1)
    scorecard["overall_rank"] = scorecard["balanced_rank_score"].rank(
        ascending=True,
        method="min",
    )
    scorecard.index.name = "strategy"
    return scorecard.sort_values(["overall_rank", "balanced_rank_score"])
