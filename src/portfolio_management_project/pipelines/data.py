"""Reproducible market-data acquisition and manifest generation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from io import StringIO
from pathlib import Path

import pandas as pd
import portfolio_management
from portfolio_management.data import DataProvider, MarketData, YahooFinanceProvider

import portfolio_management_project
from portfolio_management_project.config import ResearchConfig
from portfolio_management_project.exceptions import DataPipelineError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataBuildResult:
    """Return validated market data and its generated artifact paths."""

    market_data: MarketData
    raw_market_data_path: Path
    raw_prices_path: Path
    processed_prices_path: Path
    quality_report_path: Path
    manifest_path: Path


def run_data_pipeline(
    config: ResearchConfig,
    *,
    provider: DataProvider | None = None,
) -> DataBuildResult:
    """Download, validate, persist, and document the configured market dataset."""
    active_provider = provider or YahooFinanceProvider(
        price_field=config.data.price_field,
        auto_adjust=config.data.auto_adjust,
    )
    requested = list(config.requested_tickers)
    LOGGER.info(
        "Downloading %d assets from %s through %s.",
        len(requested),
        config.study.start_date,
        config.study.end_date,
    )

    try:
        market_data = active_provider.download(
            assets=requested,
            start_date=config.study.start_date,
            end_date=config.study.end_date,
            frequency=config.data.frequency,
        )
    except Exception as error:
        raise DataPipelineError("The configured market-data download failed.") from error

    missing_assets = [ticker for ticker in requested if ticker not in market_data.assets]
    if missing_assets:
        raise DataPipelineError(f"Provider response omitted assets: {missing_assets}.")

    validation = market_data.validate()
    validation.raise_for_errors()
    prices = market_data.prices.reindex(columns=requested)
    complete_data = market_data.data
    if complete_data is None:  # pragma: no cover - forbidden by the MarketData contract
        raise DataPipelineError("Provider returned no canonical complete market data.")
    assets_without_prices = [ticker for ticker in requested if prices[ticker].dropna().empty]
    if assets_without_prices:
        raise DataPipelineError(
            f"Provider returned no valid selected prices for assets: {assets_without_prices}."
        )

    market_bytes = _frame_to_csv_bytes(complete_data)
    price_bytes = _frame_to_csv_bytes(prices)
    data_digest = sha256(market_bytes).hexdigest()
    short_digest = data_digest[:16]

    raw_market_path = config.paths.raw / f"yahoo_market_data_{short_digest}.csv"
    raw_prices_path = config.paths.raw / f"yahoo_adjusted_close_{short_digest}.csv"
    processed_prices_path = config.paths.processed / "adjusted_close.csv"
    quality_path = config.paths.processed / "data_quality.csv"
    manifest_path = config.paths.manifests / f"market_data_{short_digest}.json"

    _write_immutable(raw_market_path, market_bytes)
    _write_immutable(raw_prices_path, price_bytes)
    _write_replaceable(processed_prices_path, price_bytes)

    quality = _quality_summary(prices)
    _write_replaceable(quality_path, _frame_to_csv_bytes(quality, include_index=True))

    manifest = {
        "schema_version": 1,
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "project_name": config.project.name,
        "project_version": portfolio_management_project.__version__,
        "library_version": portfolio_management.__version__,
        "configuration_sha256": config.config_digest,
        "market_data_sha256": data_digest,
        "selected_prices_sha256": sha256(price_bytes).hexdigest(),
        "provider": market_data.provider,
        "price_field": market_data.price_field,
        "auto_adjust": config.data.auto_adjust,
        "frequency": market_data.frequency,
        "requested_start": config.study.start_date.isoformat(),
        "requested_end_exclusive": config.study.end_date.isoformat(),
        "out_of_sample_start": config.study.out_of_sample_start.isoformat(),
        "observed_start": prices.index.min().date().isoformat(),
        "observed_end": prices.index.max().date().isoformat(),
        "rows": len(prices),
        "requested_tickers": requested,
        "investable_tickers": list(config.universe.tickers),
        "benchmark_tickers": list(config.benchmark.tickers),
        "validation": {
            "errors": [issue.__dict__ for issue in validation.errors],
            "warnings": [issue.__dict__ for issue in validation.warnings],
        },
        "missing_observations": {ticker: int(prices[ticker].isna().sum()) for ticker in requested},
    }
    _write_manifest_once(manifest_path, manifest)
    LOGGER.info("Market-data build completed with SHA-256 %s.", data_digest)

    return DataBuildResult(
        market_data=market_data,
        raw_market_data_path=raw_market_path,
        raw_prices_path=raw_prices_path,
        processed_prices_path=processed_prices_path,
        quality_report_path=quality_path,
        manifest_path=manifest_path,
    )


def _quality_summary(prices: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker in prices.columns:
        series = prices[ticker]
        valid = series.dropna()
        rows.append(
            {
                "ticker": str(ticker),
                "first_valid_date": valid.index.min().date().isoformat(),
                "last_valid_date": valid.index.max().date().isoformat(),
                "observations": int(valid.size),
                "missing_observations": int(series.isna().sum()),
                "missing_fraction": float(series.isna().mean()),
                "nonpositive_observations": int((valid <= 0.0).sum()),
            }
        )
    return pd.DataFrame(rows).set_index("ticker")


def _frame_to_csv_bytes(frame: pd.DataFrame, *, include_index: bool = True) -> bytes:
    stream = StringIO()
    frame.to_csv(
        stream,
        index=include_index,
        date_format="%Y-%m-%d",
        lineterminator="\n",
        float_format="%.12g",
    )
    return stream.getvalue().encode("utf-8")


def _write_immutable(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:  # pragma: no cover - SHA-256 collision guard
            raise DataPipelineError(f"Immutable artifact collision at {path}.")
        return
    path.write_bytes(content)


def _write_replaceable(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _write_manifest_once(path: Path, manifest: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")
