"""Tests for the thin, library-driven EDA pipeline."""

from dataclasses import replace
from pathlib import Path

import pandas as pd

from portfolio_management_project.config import DataPaths, load_research_config
from portfolio_management_project.pipelines import run_eda_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_eda_pipeline_builds_and_exports_artifacts(tmp_path: Path) -> None:
    """The project client must assemble library outputs without notebook logic."""
    config = load_research_config(PROJECT_ROOT / "configs")
    config = replace(
        config,
        paths=DataPaths(
            raw=tmp_path / "raw",
            processed=tmp_path / "processed",
            manifests=tmp_path / "manifests",
            artifacts=tmp_path / "artifacts",
        ),
    )
    index = pd.bdate_range("2020-01-01", periods=320)
    prices = pd.DataFrame(
        {
            ticker: [100.0 + position + day * (position + 1) / 100.0 for day in range(320)]
            for position, ticker in enumerate(config.universe.tickers)
        },
        index=index,
    )
    prices.iloc[100, 0] *= 1.25

    result, exported = run_eda_pipeline(config, prices=prices)

    assert result.returns.shape == (319, 9)
    assert result.correlations.shape == (9, 9)
    assert len(result.figures) == 9
    assert len(result.interpretations) == 5
    assert exported is not None
    assert exported.summary_path.is_file()
    assert (exported.tables_directory / "drawdown_summary.csv").is_file()
    assert (exported.figures_directory / "correlations.html").is_file()
