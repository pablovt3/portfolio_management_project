"""Regression checks for the methodological issues identified in the review."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from portfolio_management.risk import information_ratio

from portfolio_management_project.evaluation import realized_sharpe
from portfolio_management_project.presentation.evidence import Evidence

ROOT = Path(__file__).resolve().parents[2]


def test_realized_sharpe_uses_dated_cash_and_rejects_gaps() -> None:
    dates = pd.bdate_range("2020-01-01", periods=5)
    returns = pd.Series([0.01, -0.005, 0.002, 0.004, -0.001], index=dates)
    cash = pd.Series([0.0001, 0.0001, 0.0002, 0.0003, 0.0004], index=dates)
    excess = returns - cash
    expected = excess.mean() / excess.std(ddof=1) * np.sqrt(252)
    assert realized_sharpe(returns, cash) == pytest.approx(expected)
    assert realized_sharpe(returns, cash) == pytest.approx(information_ratio(returns, cash))
    with pytest.raises(ValueError, match="every evaluation date"):
        realized_sharpe(returns, cash.iloc[1:])
    assert np.isnan(realized_sharpe(cash, cash))


def test_published_costs_and_cash_are_consistent() -> None:
    evidence = Evidence(ROOT)
    trading = evidence.table("strategy_trading")
    assert trading.transaction_cost_rate.nunique() == 1
    assert trading.loc["benchmark_60_40", "total_transaction_cost"] > 0
    windows = evidence.table("lookback_sensitivity", 2).xs("equal_weight_quarterly", level=1)
    assert windows.sharpe_ratio.max() - windows.sharpe_ratio.min() < 1e-10
    returns = evidence.dates("strategy_returns")
    cash = evidence.dates("cash_returns").iloc[:, 0]
    performance = evidence.table("strategy_performance")
    for name in returns:
        assert performance.loc[name, "sharpe_ratio"] == pytest.approx(
            realized_sharpe(returns[name], cash),
            abs=1e-10,
        )


def test_rank_ties_do_not_depend_on_floating_point_noise() -> None:
    scores = Evidence(ROOT).table("strategy_scorecard")
    equal = scores.loc[["equal_weight_monthly", "equal_weight_quarterly"]]
    assert equal.average_max_weight_rank.nunique() == 1
    capped = scores[scores.average_max_weight.round(10) == 0.35]
    assert capped.average_max_weight_rank.nunique() == 1


def test_notebook_publication_is_clean_and_spanish_math_matches() -> None:
    english = json.loads((ROOT / "notebooks/portfolio_optimization_study.ipynb").read_text())
    code = [cell for cell in english["cells"] if cell["cell_type"] == "code"]
    assert all(not cell["outputs"] and cell["execution_count"] is None for cell in code)
    path = ROOT / "notebooks/portfolio_optimization_study.es.ipynb"
    if path.is_file():
        spanish = json.loads(path.read_text())
        translated = [cell for cell in spanish["cells"] if cell["cell_type"] == "code"]
        assert len(code) == len(translated)
        for first, second in zip(code, translated, strict=True):
            assert "".join(first["source"]).replace("'en'", "'es'") == "".join(second["source"])


def test_evidence_rejects_changed_configuration(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(ROOT / "configs", tmp_path / "configs")
    target = tmp_path / "reports/data"
    target.mkdir(parents=True)
    manifest = json.loads((ROOT / "reports/data/study_manifest.json").read_text())
    manifest["config_digest"] = "different"
    (target / "study_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="assumptions changed"):
        Evidence(tmp_path)
