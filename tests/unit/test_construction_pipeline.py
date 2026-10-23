"""Tests for static classical portfolio construction."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_management_project.config import DataPaths, load_research_config
from portfolio_management_project.pipelines import run_construction_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_construction_pipeline_runs_every_supported_model(tmp_path: Path) -> None:
    """The project must consume every current classical model through the facade."""
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
    generator = np.random.default_rng(7)
    observations = 900
    tickers = config.universe.tickers
    means = np.array(
        [0.00040, 0.00030, 0.00035, 0.00012, 0.00015, 0.00020, 0.00028, 0.00025, 0.00004]
    )
    innovations = generator.normal(means, 0.006, size=(observations, len(tickers)))
    prices = pd.DataFrame(
        100.0 * np.cumprod(1.0 + innovations, axis=0),
        index=pd.bdate_range("2011-01-03", periods=observations),
        columns=tickers,
    )

    result, exported = run_construction_pipeline(config, prices=prices)

    assert set(result.optimizations) == {
        "equal_weight",
        "minimum_variance",
        "mean_variance",
        "target_return",
        "maximum_sharpe",
    }
    assert result.weights.shape == (9, 5)
    assert np.allclose(result.weights.sum(), 1.0)
    assert len(result.frontier.expected_returns) == 60
    assert exported is not None
    assert exported.summary_path.is_file()
    assert (exported.figures_directory / "efficient_frontier.html").is_file()
