"""Typed, validated configuration for the research project."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProjectSettings:
    """Identify the research project and its reporting currency."""

    name: str
    base_currency: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Project name cannot be empty.")
        if len(self.base_currency.strip()) != 3:
            raise ValueError("Base currency must be a three-letter code.")


@dataclass(frozen=True)
class StudySettings:
    """Define the historical and out-of-sample study dates."""

    start_date: date
    end_date: date
    out_of_sample_start: date

    def __post_init__(self) -> None:
        if self.end_date <= self.start_date:
            raise ValueError("Study end date must be after the start date.")
        if not self.start_date < self.out_of_sample_start < self.end_date:
            raise ValueError("Out-of-sample start must fall inside the study period.")


@dataclass(frozen=True)
class DataSettings:
    """Define the provider and price request."""

    provider: str
    frequency: str
    price_field: str
    auto_adjust: bool

    def __post_init__(self) -> None:
        if self.provider != "yahoo_finance":
            raise ValueError("The initial pipeline supports only 'yahoo_finance'.")
        if not self.frequency.strip():
            raise ValueError("Data frequency cannot be empty.")
        if not self.price_field.strip():
            raise ValueError("Price field cannot be empty.")


@dataclass(frozen=True)
class EDASettings:
    """Define reusable EDA windows and diagnostic choices."""

    periods_per_year: int
    rolling_volatility_window: int
    rolling_return_window: int
    rolling_correlation_window: int
    rolling_correlation_assets: tuple[str, str]
    outlier_method: str
    outlier_threshold: float

    def __post_init__(self) -> None:
        windows = (
            self.periods_per_year,
            self.rolling_volatility_window,
            self.rolling_return_window,
            self.rolling_correlation_window,
        )
        if any(not isinstance(value, int) or value < 2 for value in windows):
            raise ValueError("EDA periods and rolling windows must be integers of at least 2.")
        if self.rolling_correlation_assets[0] == self.rolling_correlation_assets[1]:
            raise ValueError("Rolling-correlation assets must be different.")
        if self.outlier_method not in ("iqr", "zscore"):
            raise ValueError("EDA outlier method must be 'iqr' or 'zscore'.")
        if self.outlier_threshold <= 0.0:
            raise ValueError("EDA outlier threshold must be strictly positive.")


@dataclass(frozen=True)
class PortfolioConstructionSettings:
    """Define the primary static portfolio-construction specification."""

    sample_start: date
    periods_per_year: int
    expected_return_estimator: str
    covariance_estimator: str
    risk_free_asset: str
    min_weight: float
    max_weight: float
    risk_aversion: float
    target_return: float
    frontier_portfolios: int

    def __post_init__(self) -> None:
        if self.periods_per_year < 2 or self.frontier_portfolios < 2:
            raise ValueError("Portfolio periods and frontier size must be at least 2.")
        if self.expected_return_estimator != "historical_mean":
            raise ValueError("The primary expected-return estimator must be 'historical_mean'.")
        if self.covariance_estimator != "ledoit_wolf":
            raise ValueError("The primary covariance estimator must be 'ledoit_wolf'.")
        if not 0.0 <= self.min_weight < self.max_weight <= 1.0:
            raise ValueError("Portfolio weight bounds must satisfy 0 <= min < max <= 1.")
        if self.risk_aversion <= 0.0:
            raise ValueError("Risk aversion must be strictly positive.")


@dataclass(frozen=True)
class BacktestingSettings:
    """Define the dynamic out-of-sample backtesting specification."""

    lookback_periods: int
    rebalance_frequencies: tuple[str, ...]
    transaction_cost_bps: float
    initial_value: float
    strategies: tuple[str, ...]
    band_thresholds: tuple[float, ...] = ()
    band_estimation_frequency: str = "monthly"

    def __post_init__(self) -> None:
        if not isinstance(self.lookback_periods, int) or self.lookback_periods < 2:
            raise ValueError("Backtest lookback_periods must be an integer of at least 2.")
        allowed_frequencies = {"monthly", "quarterly"}
        if not self.rebalance_frequencies:
            raise ValueError("At least one rebalance frequency is required.")
        if len(set(self.rebalance_frequencies)) != len(self.rebalance_frequencies):
            raise ValueError("Backtest rebalance frequencies cannot be duplicated.")
        if not set(self.rebalance_frequencies).issubset(allowed_frequencies):
            raise ValueError("Backtest frequencies must be monthly or quarterly.")
        if not 0.0 <= self.transaction_cost_bps < 10_000.0:
            raise ValueError("Transaction-cost basis points must be in [0, 10000).")
        if self.initial_value <= 0.0:
            raise ValueError("Backtest initial value must be strictly positive.")
        allowed_strategies = {
            "equal_weight",
            "minimum_variance",
            "mean_variance",
            "target_return",
            "maximum_sharpe",
        }
        if not self.strategies:
            raise ValueError("At least one backtest strategy is required.")
        if len(set(self.strategies)) != len(self.strategies):
            raise ValueError("Backtest strategies cannot be duplicated.")
        if not set(self.strategies).issubset(allowed_strategies):
            raise ValueError("Backtest strategies must use supported library models.")
        if len(set(self.band_thresholds)) != len(self.band_thresholds):
            raise ValueError("Backtest band thresholds cannot be duplicated.")
        if any(not 0.0 < value < 1.0 for value in self.band_thresholds):
            raise ValueError("Backtest band thresholds must lie in (0, 1).")
        if self.band_estimation_frequency not in allowed_frequencies:
            raise ValueError("Band estimation frequency must be monthly or quarterly.")


@dataclass(frozen=True)
class RegimeSettings:
    """Define one named historical evaluation regime."""

    name: str
    label: str
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.label.strip():
            raise ValueError("Regime name and label cannot be empty.")
        if self.end_date < self.start_date:
            raise ValueError("Regime end date cannot precede its start date.")


@dataclass(frozen=True)
class RobustnessSettings:
    """Define sensitivity scenarios and regime-analysis controls."""

    cost_scenarios_bps: tuple[float, ...]
    lookback_scenarios: tuple[int, ...]
    max_weight_scenarios: tuple[float, ...]
    primary_frequency: str
    drawdown_episodes: int
    regimes: tuple[RegimeSettings, ...]

    def __post_init__(self) -> None:
        if not self.cost_scenarios_bps or any(
            value < 0.0 or value >= 10_000.0 for value in self.cost_scenarios_bps
        ):
            raise ValueError("Robustness cost scenarios must be in [0, 10000).")
        if not self.lookback_scenarios or any(
            not isinstance(value, int) or value < 2 for value in self.lookback_scenarios
        ):
            raise ValueError("Robustness lookbacks must be integers of at least 2.")
        if not self.max_weight_scenarios or any(
            not 0.0 < value <= 1.0 for value in self.max_weight_scenarios
        ):
            raise ValueError("Robustness maximum weights must lie in (0, 1].")
        if self.primary_frequency not in {"monthly", "quarterly"}:
            raise ValueError("Robustness primary frequency must be monthly or quarterly.")
        if not isinstance(self.drawdown_episodes, int) or self.drawdown_episodes < 1:
            raise ValueError("drawdown_episodes must be a positive integer.")
        if not self.regimes:
            raise ValueError("At least one historical regime is required.")
        names = [regime.name for regime in self.regimes]
        if len(names) != len(set(names)):
            raise ValueError("Historical regime names cannot be duplicated.")
        ordered = sorted(self.regimes, key=lambda regime: regime.start_date)
        if any(
            current.start_date <= previous.end_date
            for previous, current in zip(ordered, ordered[1:], strict=False)
        ):
            raise ValueError("Historical regimes cannot overlap.")


@dataclass(frozen=True)
class DataPaths:
    """Contain project output directories."""

    raw: Path
    processed: Path
    manifests: Path
    artifacts: Path


@dataclass(frozen=True)
class AssetDefinition:
    """Describe one governed investable-universe asset."""

    ticker: str
    name: str
    sleeve: str
    role: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("ticker", self.ticker),
            ("name", self.name),
            ("sleeve", self.sleeve),
            ("role", self.role),
        ):
            if not value.strip():
                raise ValueError(f"Asset {field_name} cannot be empty.")


@dataclass(frozen=True)
class UniverseDefinition:
    """Contain the governed opportunity set and explicit exclusions."""

    methodology: str
    selection_as_of: date
    base_currency: str
    assets: tuple[AssetDefinition, ...]
    exclusions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.assets:
            raise ValueError("The investable universe cannot be empty.")
        tickers = [asset.ticker for asset in self.assets]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Investable-universe tickers cannot be duplicated.")
        sleeves = [asset.sleeve for asset in self.assets]
        if len(sleeves) != len(set(sleeves)):
            raise ValueError("The initial universe requires one ETF per sleeve.")

    @property
    def tickers(self) -> tuple[str, ...]:
        """Return investable tickers in governed order."""
        return tuple(asset.ticker for asset in self.assets)


@dataclass(frozen=True)
class BenchmarkConstituent:
    """Define one benchmark constituent and target weight."""

    ticker: str
    weight: float

    def __post_init__(self) -> None:
        if not self.ticker.strip():
            raise ValueError("Benchmark ticker cannot be empty.")
        if not 0.0 < self.weight <= 1.0:
            raise ValueError("Benchmark weights must be in (0, 1].")


@dataclass(frozen=True)
class BenchmarkDefinition:
    """Define the external policy benchmark and cash hurdle."""

    name: str
    description: str
    rebalance_frequency: str
    constituents: tuple[BenchmarkConstituent, ...]
    cash_hurdle: str

    def __post_init__(self) -> None:
        if not self.constituents:
            raise ValueError("Benchmark constituents cannot be empty.")
        tickers = [item.ticker for item in self.constituents]
        if len(tickers) != len(set(tickers)):
            raise ValueError("Benchmark tickers cannot be duplicated.")
        if abs(sum(item.weight for item in self.constituents) - 1.0) > 1e-10:
            raise ValueError("Benchmark weights must sum to one.")

    @property
    def tickers(self) -> tuple[str, ...]:
        """Return benchmark tickers in configured order."""
        return tuple(item.ticker for item in self.constituents)


@dataclass(frozen=True)
class ResearchConfig:
    """Aggregate all validated project configuration."""

    project: ProjectSettings
    study: StudySettings
    data: DataSettings
    eda: EDASettings
    portfolio_construction: PortfolioConstructionSettings
    backtesting: BacktestingSettings
    robustness: RobustnessSettings
    paths: DataPaths
    universe: UniverseDefinition
    benchmark: BenchmarkDefinition
    config_digest: str

    def __post_init__(self) -> None:
        if self.project.base_currency != self.universe.base_currency:
            raise ValueError("Project and universe base currencies must match.")
        if self.benchmark.cash_hurdle not in self.universe.tickers:
            raise ValueError("The cash hurdle must belong to the investable universe.")
        unknown_rolling_assets = [
            ticker
            for ticker in self.eda.rolling_correlation_assets
            if ticker not in self.universe.tickers
        ]
        if unknown_rolling_assets:
            raise ValueError(
                f"Rolling-correlation assets must belong to the universe: {unknown_rolling_assets}."
            )
        if self.portfolio_construction.risk_free_asset not in self.universe.tickers:
            raise ValueError("The construction risk-free asset must belong to the universe.")
        if not (
            self.study.start_date <= self.portfolio_construction.sample_start < self.study.end_date
        ):
            raise ValueError("Portfolio sample start must fall inside the study period.")
        if any(
            regime.start_date < self.study.out_of_sample_start
            or regime.end_date >= self.study.end_date
            for regime in self.robustness.regimes
        ):
            raise ValueError("Historical regimes must lie inside the out-of-sample period.")

    @property
    def requested_tickers(self) -> tuple[str, ...]:
        """Return a deduplicated provider request in deterministic order."""
        return tuple(dict.fromkeys((*self.universe.tickers, *self.benchmark.tickers)))


def load_research_config(config_dir: Path) -> ResearchConfig:
    """Load and validate the project YAML files from ``config_dir``."""
    config_dir = config_dir.resolve()
    base = _load_mapping(config_dir / "base.yaml")
    universe_data = _load_mapping(config_dir / "universe.yaml")
    benchmark_data = _load_mapping(config_dir / "benchmark.yaml")

    project_data = _mapping(base.get("project"), "base.project")
    study_data = _mapping(base.get("study"), "base.study")
    data_data = _mapping(base.get("data"), "base.data")
    eda_data = _mapping(base.get("eda"), "base.eda")
    construction_data = _mapping(base.get("portfolio_construction"), "base.portfolio_construction")
    backtesting_data = _mapping(base.get("backtesting"), "base.backtesting")
    robustness_data = _mapping(base.get("robustness"), "base.robustness")
    path_data = _mapping(base.get("paths"), "base.paths")
    project_root = config_dir.parent

    project = ProjectSettings(
        name=_string(project_data.get("name"), "base.project.name"),
        base_currency=_string(
            project_data.get("base_currency"), "base.project.base_currency"
        ).upper(),
    )
    study = StudySettings(
        start_date=_date(study_data.get("start_date"), "base.study.start_date"),
        end_date=_date(study_data.get("end_date"), "base.study.end_date"),
        out_of_sample_start=_date(
            study_data.get("out_of_sample_start"), "base.study.out_of_sample_start"
        ),
    )
    data = DataSettings(
        provider=_string(data_data.get("provider"), "base.data.provider"),
        frequency=_string(data_data.get("frequency"), "base.data.frequency"),
        price_field=_string(data_data.get("price_field"), "base.data.price_field"),
        auto_adjust=_boolean(data_data.get("auto_adjust"), "base.data.auto_adjust"),
    )
    rolling_assets = _sequence(
        eda_data.get("rolling_correlation_assets"),
        "base.eda.rolling_correlation_assets",
    )
    if len(rolling_assets) != 2:
        raise ValueError("Exactly two rolling-correlation assets are required.")
    eda = EDASettings(
        periods_per_year=_integer(eda_data.get("periods_per_year"), "base.eda.periods_per_year"),
        rolling_volatility_window=_integer(
            eda_data.get("rolling_volatility_window"),
            "base.eda.rolling_volatility_window",
        ),
        rolling_return_window=_integer(
            eda_data.get("rolling_return_window"), "base.eda.rolling_return_window"
        ),
        rolling_correlation_window=_integer(
            eda_data.get("rolling_correlation_window"),
            "base.eda.rolling_correlation_window",
        ),
        rolling_correlation_assets=(
            _string(rolling_assets[0], "base.eda.rolling_correlation_assets[0]"),
            _string(rolling_assets[1], "base.eda.rolling_correlation_assets[1]"),
        ),
        outlier_method=_string(eda_data.get("outlier_method"), "base.eda.outlier_method"),
        outlier_threshold=_number(eda_data.get("outlier_threshold"), "base.eda.outlier_threshold"),
    )
    construction = PortfolioConstructionSettings(
        sample_start=_date(
            construction_data.get("sample_start"),
            "base.portfolio_construction.sample_start",
        ),
        periods_per_year=_integer(
            construction_data.get("periods_per_year"),
            "base.portfolio_construction.periods_per_year",
        ),
        expected_return_estimator=_string(
            construction_data.get("expected_return_estimator"),
            "base.portfolio_construction.expected_return_estimator",
        ),
        covariance_estimator=_string(
            construction_data.get("covariance_estimator"),
            "base.portfolio_construction.covariance_estimator",
        ),
        risk_free_asset=_string(
            construction_data.get("risk_free_asset"),
            "base.portfolio_construction.risk_free_asset",
        ),
        min_weight=_number(
            construction_data.get("min_weight"),
            "base.portfolio_construction.min_weight",
        ),
        max_weight=_number(
            construction_data.get("max_weight"),
            "base.portfolio_construction.max_weight",
        ),
        risk_aversion=_number(
            construction_data.get("risk_aversion"),
            "base.portfolio_construction.risk_aversion",
        ),
        target_return=_number(
            construction_data.get("target_return"),
            "base.portfolio_construction.target_return",
        ),
        frontier_portfolios=_integer(
            construction_data.get("frontier_portfolios"),
            "base.portfolio_construction.frontier_portfolios",
        ),
    )
    backtesting = BacktestingSettings(
        lookback_periods=_integer(
            backtesting_data.get("lookback_periods"),
            "base.backtesting.lookback_periods",
        ),
        rebalance_frequencies=tuple(
            _string(value, "base.backtesting.rebalance_frequencies[]")
            for value in _sequence(
                backtesting_data.get("rebalance_frequencies"),
                "base.backtesting.rebalance_frequencies",
            )
        ),
        transaction_cost_bps=_number(
            backtesting_data.get("transaction_cost_bps"),
            "base.backtesting.transaction_cost_bps",
        ),
        initial_value=_number(
            backtesting_data.get("initial_value"),
            "base.backtesting.initial_value",
        ),
        strategies=tuple(
            _string(value, "base.backtesting.strategies[]")
            for value in _sequence(
                backtesting_data.get("strategies"),
                "base.backtesting.strategies",
            )
        ),
        band_thresholds=tuple(
            _number(value, "base.backtesting.band_thresholds[]")
            for value in _sequence(
                backtesting_data.get("band_thresholds", ()),
                "base.backtesting.band_thresholds",
            )
        ),
        band_estimation_frequency=_string(
            backtesting_data.get("band_estimation_frequency", "monthly"),
            "base.backtesting.band_estimation_frequency",
        ),
    )
    regime_rows = _sequence(
        robustness_data.get("regimes"),
        "base.robustness.regimes",
    )
    regimes = tuple(
        RegimeSettings(
            name=_string(
                _mapping(row, "base.robustness.regimes[]").get("name"),
                "regime.name",
            ),
            label=_string(
                _mapping(row, "base.robustness.regimes[]").get("label"),
                "regime.label",
            ),
            start_date=_date(
                _mapping(row, "base.robustness.regimes[]").get("start_date"),
                "regime.start_date",
            ),
            end_date=_date(
                _mapping(row, "base.robustness.regimes[]").get("end_date"),
                "regime.end_date",
            ),
        )
        for row in regime_rows
    )
    robustness = RobustnessSettings(
        cost_scenarios_bps=tuple(
            _number(value, "base.robustness.cost_scenarios_bps[]")
            for value in _sequence(
                robustness_data.get("cost_scenarios_bps"),
                "base.robustness.cost_scenarios_bps",
            )
        ),
        lookback_scenarios=tuple(
            _integer(value, "base.robustness.lookback_scenarios[]")
            for value in _sequence(
                robustness_data.get("lookback_scenarios"),
                "base.robustness.lookback_scenarios",
            )
        ),
        max_weight_scenarios=tuple(
            _number(value, "base.robustness.max_weight_scenarios[]")
            for value in _sequence(
                robustness_data.get("max_weight_scenarios"),
                "base.robustness.max_weight_scenarios",
            )
        ),
        primary_frequency=_string(
            robustness_data.get("primary_frequency"),
            "base.robustness.primary_frequency",
        ),
        drawdown_episodes=_integer(
            robustness_data.get("drawdown_episodes"),
            "base.robustness.drawdown_episodes",
        ),
        regimes=regimes,
    )
    paths = DataPaths(
        raw=_project_path(project_root, path_data.get("raw"), "base.paths.raw"),
        processed=_project_path(project_root, path_data.get("processed"), "base.paths.processed"),
        manifests=_project_path(project_root, path_data.get("manifests"), "base.paths.manifests"),
        artifacts=_project_path(project_root, path_data.get("artifacts"), "base.paths.artifacts"),
    )

    asset_rows = _sequence(universe_data.get("assets"), "universe.assets")
    assets = tuple(
        AssetDefinition(
            ticker=_string(_mapping(row, "universe.assets[]").get("ticker"), "ticker"),
            name=_string(_mapping(row, "universe.assets[]").get("name"), "name"),
            sleeve=_string(_mapping(row, "universe.assets[]").get("sleeve"), "sleeve"),
            role=_string(_mapping(row, "universe.assets[]").get("role"), "role"),
        )
        for row in asset_rows
    )
    universe = UniverseDefinition(
        methodology=_string(universe_data.get("methodology"), "universe.methodology"),
        selection_as_of=_date(universe_data.get("selection_as_of"), "universe.selection_as_of"),
        base_currency=_string(universe_data.get("base_currency"), "universe.base_currency").upper(),
        assets=assets,
        exclusions=tuple(
            _string(value, "universe.exclusions[]")
            for value in _sequence(universe_data.get("exclusions"), "universe.exclusions")
        ),
    )

    constituent_rows = _sequence(benchmark_data.get("constituents"), "benchmark.constituents")
    constituents = tuple(
        BenchmarkConstituent(
            ticker=_string(_mapping(row, "benchmark.constituents[]").get("ticker"), "ticker"),
            weight=_number(_mapping(row, "benchmark.constituents[]").get("weight"), "weight"),
        )
        for row in constituent_rows
    )
    benchmark = BenchmarkDefinition(
        name=_string(benchmark_data.get("name"), "benchmark.name"),
        description=_string(benchmark_data.get("description"), "benchmark.description"),
        rebalance_frequency=_string(
            benchmark_data.get("rebalance_frequency"), "benchmark.rebalance_frequency"
        ),
        constituents=constituents,
        cash_hurdle=_string(benchmark_data.get("cash_hurdle"), "benchmark.cash_hurdle"),
    )

    digest = sha256()
    for path in sorted(config_dir.glob("*.yaml")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())

    return ResearchConfig(
        project=project,
        study=study,
        data=data,
        eda=eda,
        portfolio_construction=construction,
        backtesting=backtesting,
        robustness=robustness,
        paths=paths,
        universe=universe,
        benchmark=benchmark,
        config_digest=digest.hexdigest(),
    )


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file does not exist: {path}")
    with path.open(encoding="utf-8") as stream:
        return _mapping(yaml.safe_load(stream), str(path))


def _mapping(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{context} must be a mapping.")
    return dict(value)


def _sequence(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{context} must be a list.")
    return list(value)


def _string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{context} must be a non-empty string.")
    return value.strip()


def _boolean(value: object, context: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{context} must be a boolean.")
    return value


def _number(value: object, context: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise TypeError(f"{context} must be numeric.")
    return float(value)


def _integer(value: object, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{context} must be an integer.")
    return value


def _date(value: object, context: str) -> date:
    text = _string(value, context)
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{context} must use YYYY-MM-DD format.") from error


def _project_path(project_root: Path, value: object, context: str) -> Path:
    relative = Path(_string(value, context))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{context} must be a safe project-relative path.")
    return (project_root / relative).resolve()
