"""Tests for dynamic out-of-sample portfolio backtesting."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_management_project.config import (
    DataPaths,
    RegimeSettings,
    StudySettings,
    load_research_config,
)
from portfolio_management_project.pipelines import run_backtesting_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_backtesting_pipeline_runs_all_models_and_frequencies(tmp_path: Path) -> None:
    """Every configured model must run on a common no-look-ahead calendar."""
    config = load_research_config(PROJECT_ROOT / "configs")
    config = replace(
        config,
        study=StudySettings(
            start_date=date(2020, 1, 1),
            end_date=date(2022, 1, 1),
            out_of_sample_start=date(2021, 1, 4),
        ),
        backtesting=replace(config.backtesting, lookback_periods=80),
        portfolio_construction=replace(
            config.portfolio_construction,
            sample_start=date(2020, 1, 2),
            target_return=0.05,
        ),
        robustness=replace(
            config.robustness,
            regimes=(
                RegimeSettings(
                    "test_period",
                    "Test Period",
                    date(2021, 1, 4),
                    date(2021, 12, 31),
                ),
            ),
        ),
        paths=DataPaths(
            raw=tmp_path / "raw",
            processed=tmp_path / "processed",
            manifests=tmp_path / "manifests",
            artifacts=tmp_path / "artifacts",
        ),
    )
    generator = np.random.default_rng(19)
    observations = 430
    tickers = config.requested_tickers
    means = np.array(
        [
            0.00040,
            0.00030,
            0.00035,
            0.00012,
            0.00015,
            0.00020,
            0.00028,
            0.00025,
            0.00002,
            0.00032,
            0.00010,
        ]
    )
    volatilities = np.full(len(tickers), 0.004)
    volatilities[tickers.index("BIL")] = 0.00005
    innovations = generator.normal(
        means,
        volatilities,
        size=(observations, len(tickers)),
    )
    prices = pd.DataFrame(
        100.0 * np.cumprod(1.0 + innovations, axis=0),
        index=pd.bdate_range("2020-01-02", periods=observations),
        columns=tickers,
    )

    result, exported = run_backtesting_pipeline(config, prices=prices)

    assert len(result.strategies) == 25
    assert result.comparison.number_of_strategies == 26
    assert "equal_weight_band_500bp" in result.strategies
    reference_index = next(iter(result.strategies.values())).returns.index
    assert result.benchmark.returns.index.equals(reference_index)
    for strategy in result.strategies.values():
        assert strategy.returns.index.equals(reference_index)
        assert strategy.estimation_windows is not None
        assert (
            strategy.estimation_windows["estimation_end"]
            < strategy.estimation_windows.index.to_series()
        ).all()
        assert strategy.transaction_costs is not None
        assert strategy.target_weights_history is not None
    band = result.strategies["equal_weight_band_500bp"]
    assert band.rebalance_trigger == "threshold"
    assert band.rebalance_threshold == 0.05
    assert (
        int(band.summary()["number_of_rebalances"])
        <= int(
            result.strategies["equal_weight_monthly"].summary()["number_of_rebalances"]
        )
    )
    assert exported is not None
    assert exported.summary_path.is_file()
    assert (exported.tables_directory / "estimation_windows.csv").is_file()
    assert (exported.figures_directory / "strategy_wealth.html").is_file()
