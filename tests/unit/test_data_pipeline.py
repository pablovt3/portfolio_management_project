"""Tests for the reproducible data pipeline."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from portfolio_management.data import DataProvider, MarketData

from portfolio_management_project.config import DataPaths, ResearchConfig, load_research_config
from portfolio_management_project.exceptions import DataPipelineError
from portfolio_management_project.pipelines import run_data_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FakeProvider(DataProvider):
    """Return deterministic market data without network access."""

    def __init__(self, *, omit_last_asset: bool = False, all_missing: bool = False) -> None:
        self.omit_last_asset = omit_last_asset
        self.all_missing = all_missing

    def download(
        self,
        assets: list[str],
        start_date: date | str,
        end_date: date | str | None = None,
        frequency: str = "1d",
    ) -> MarketData:
        """Build a small deterministic adjusted-close matrix."""
        del start_date, end_date
        selected_assets = assets[:-1] if self.omit_last_asset else assets
        index = pd.date_range("2020-01-02", periods=4, freq="B", name="date")
        prices = pd.DataFrame(
            {
                ticker: [100.0 + position + offset for offset in range(4)]
                for position, ticker in enumerate(selected_assets)
            },
            index=index,
        )
        if self.all_missing:
            prices.loc[:, selected_assets[0]] = float("nan")
        return MarketData(
            prices=prices,
            provider="fake",
            price_field="adjusted_close",
            frequency=frequency,
        )


class FailingProvider(DataProvider):
    """Raise a deterministic provider error."""

    def download(
        self,
        assets: list[str],
        start_date: date | str,
        end_date: date | str | None = None,
        frequency: str = "1d",
    ) -> MarketData:
        """Simulate an upstream failure."""
        del assets, start_date, end_date, frequency
        raise ConnectionError("simulated provider failure")


def _temporary_config(tmp_path: Path) -> ResearchConfig:
    config = load_research_config(PROJECT_ROOT / "configs")
    return replace(
        config,
        paths=DataPaths(
            raw=tmp_path / "raw",
            processed=tmp_path / "processed",
            manifests=tmp_path / "manifests",
            artifacts=tmp_path / "artifacts",
        ),
    )


def test_pipeline_writes_hashed_raw_data_and_manifest(tmp_path: Path) -> None:
    """A deterministic provider must produce an auditable data build."""
    config = _temporary_config(tmp_path)
    result = run_data_pipeline(config, provider=FakeProvider())

    assert result.raw_market_data_path.is_file()
    assert result.raw_prices_path.is_file()
    assert result.processed_prices_path.is_file()
    assert result.quality_report_path.is_file()
    assert result.manifest_path.is_file()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["rows"] == 4
    assert manifest["requested_tickers"] == list(config.requested_tickers)
    assert len(manifest["market_data_sha256"]) == 64
    assert set(manifest["missing_observations"].values()) == {0}

    repeated = run_data_pipeline(config, provider=FakeProvider())
    assert repeated.raw_market_data_path == result.raw_market_data_path
    assert repeated.manifest_path == result.manifest_path


def test_pipeline_rejects_an_incomplete_provider_response(tmp_path: Path) -> None:
    """All governed assets must be present before artifacts are written."""
    config = _temporary_config(tmp_path)

    with pytest.raises(DataPipelineError, match="omitted assets"):
        run_data_pipeline(config, provider=FakeProvider(omit_last_asset=True))


def test_pipeline_wraps_provider_failures(tmp_path: Path) -> None:
    """Upstream exceptions must be exposed through the project error boundary."""
    config = _temporary_config(tmp_path)

    with pytest.raises(DataPipelineError, match="download failed"):
        run_data_pipeline(config, provider=FailingProvider())


def test_pipeline_rejects_assets_without_valid_prices(tmp_path: Path) -> None:
    """A returned ticker must contain at least one usable selected price."""
    config = _temporary_config(tmp_path)

    with pytest.raises(DataPipelineError, match="no valid selected prices"):
        run_data_pipeline(config, provider=FakeProvider(all_missing=True))
