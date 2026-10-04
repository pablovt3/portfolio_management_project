"""Tests for robustness, diagnostic, and balanced-scorecard research."""

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
from portfolio_management_project.pipelines import (
    build_publication_report,
    run_backtesting_pipeline,
    run_construction_pipeline,
    run_eda_pipeline,
    run_robustness_pipeline,
)
from portfolio_management_project.pipelines.reporting import _strategy_label

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_strategy_labels_are_publication_ready() -> None:
    """Internal identifiers must become readable labels in public reports."""
    assert _strategy_label("benchmark_60_40") == "Global 60/40"
    assert _strategy_label("target_return_quarterly") == "Target Return Quarterly"
    assert _strategy_label("target_return_band_500bp") == "Target Return Band 500Bp"


def test_robustness_pipeline_produces_all_research_dimensions(tmp_path: Path) -> None:
    """The study must quantify episodes, regimes, sensitivity, and stability."""
    config = load_research_config(PROJECT_ROOT / "configs")
    config = replace(
        config,
        study=StudySettings(
            start_date=date(2020, 1, 1),
            end_date=date(2022, 1, 1),
            out_of_sample_start=date(2021, 1, 4),
        ),
        portfolio_construction=replace(
            config.portfolio_construction,
            sample_start=date(2020, 1, 2),
            target_return=0.05,
        ),
        backtesting=replace(config.backtesting, lookback_periods=80),
        robustness=replace(
            config.robustness,
            cost_scenarios_bps=(0.0, 10.0),
            lookback_scenarios=(40, 80),
            max_weight_scenarios=(0.35, 0.50),
            drawdown_episodes=2,
            regimes=(
                RegimeSettings(
                    "first_half",
                    "First Half",
                    date(2021, 1, 4),
                    date(2021, 6, 30),
                ),
                RegimeSettings(
                    "second_half",
                    "Second Half",
                    date(2021, 7, 1),
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
    generator = np.random.default_rng(29)
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

    baseline, _ = run_backtesting_pipeline(config, prices=prices, export=False)
    result, exported = run_robustness_pipeline(
        config,
        prices=prices,
        baseline=baseline,
    )

    assert not result.drawdown_episodes.empty
    assert result.drawdown_episodes.groupby(level="strategy").size().max() <= 2
    assert (result.drawdown_episodes["depth"] >= 0.0).all()
    assert len(result.concentration_summary) == 25
    assert (result.concentration_summary["average_effective_assets"] >= 1.0).all()
    assert set(result.regime_performance.index.get_level_values("regime")) == {
        "first_half",
        "second_half",
    }
    assert set(result.cost_sensitivity.index.get_level_values("cost_bps")) == {
        0.0,
        10.0,
    }
    assert set(result.lookback_sensitivity.index.get_level_values("lookback_periods")) == {40, 80}
    assert set(result.weight_cap_sensitivity.index.get_level_values("max_weight")) == {
        0.35,
        0.50,
    }
    assert result.scorecard["overall_rank"].min() == 1.0
    assert exported is not None
    assert exported.summary_path.is_file()
    assert (exported.tables_directory / "strategy_scorecard.csv").is_file()

    eda, _ = run_eda_pipeline(config, prices=prices, export=False)
    construction, _ = run_construction_pipeline(config, prices=prices, export=False)
    report = build_publication_report(
        config,
        eda,
        construction,
        baseline,
        result,
        save_images=True,
    )
    assert report.markdown_report.is_file()
    assert report.html_report.is_file()
    assert (report.figures_directory / "strategy_wealth.png").stat().st_size > 10000
    assert len(report.key_findings) == 6
    assert (report.data_directory / "study_manifest.json").is_file()
    html = report.html_report.read_text(encoding="utf-8")
    assert "plotly-graph-div" in html
    assert "Decision framework" in html
    assert "Compact strategy snapshot" in html
    assert "annualized_return" not in html
