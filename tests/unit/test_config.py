"""Tests for project configuration and universe governance."""

import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
import yaml

from portfolio_management_project.config import (
    AssetDefinition,
    BacktestingSettings,
    BenchmarkConstituent,
    BenchmarkDefinition,
    DataSettings,
    ProjectSettings,
    RegimeSettings,
    RobustnessSettings,
    StudySettings,
    UniverseDefinition,
    load_research_config,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_checked_in_configuration_loads() -> None:
    """The governed project configuration must be internally consistent."""
    config = load_research_config(PROJECT_ROOT / "configs")

    assert config.data.price_field == "Adj Close"
    assert config.data.auto_adjust is False
    assert config.universe.tickers == (
        "VTI",
        "VEA",
        "VWO",
        "IEF",
        "TIP",
        "LQD",
        "VNQ",
        "GLD",
        "BIL",
    )
    assert config.benchmark.tickers == ("VT", "BND")
    assert config.eda.rolling_correlation_assets == ("VTI", "IEF")
    assert config.eda.periods_per_year == 252
    assert config.portfolio_construction.max_weight == 0.35
    assert config.portfolio_construction.target_return == 0.07
    assert config.backtesting.lookback_periods == 756
    assert config.backtesting.rebalance_frequencies == ("monthly", "quarterly")
    assert config.backtesting.band_thresholds == (0.025, 0.05, 0.075)
    assert config.backtesting.band_estimation_frequency == "monthly"
    assert config.backtesting.transaction_cost_bps == 10.0
    assert config.robustness.lookback_scenarios == (252, 504, 756, 1008, 1260)
    assert config.robustness.cost_scenarios_bps == (0.0, 5.0, 10.0, 15.0, 20.0, 25.0)
    assert config.robustness.max_weight_scenarios == (
        0.20,
        0.25,
        0.30,
        0.35,
        0.40,
        0.50,
    )
    assert len(config.robustness.regimes) == 4
    assert config.requested_tickers[-2:] == ("VT", "BND")
    assert len(config.config_digest) == 64


def test_benchmark_weights_must_sum_to_one() -> None:
    """Invalid policy weights must fail during configuration construction."""
    with pytest.raises(ValueError, match="sum to one"):
        BenchmarkDefinition(
            name="Invalid",
            description="Invalid benchmark",
            rebalance_frequency="quarterly",
            constituents=(
                BenchmarkConstituent("VT", 0.60),
                BenchmarkConstituent("BND", 0.30),
            ),
            cash_hurdle="BIL",
        )


def test_backtesting_settings_reject_invalid_values() -> None:
    """Invalid dynamic-research choices must fail at configuration loading."""
    with pytest.raises(ValueError, match="lookback"):
        BacktestingSettings(1, ("monthly",), 10.0, 100.0, ("equal_weight",))
    with pytest.raises(ValueError, match="monthly or quarterly"):
        BacktestingSettings(60, ("weekly",), 10.0, 100.0, ("equal_weight",))
    with pytest.raises(ValueError, match="supported library models"):
        BacktestingSettings(60, ("monthly",), 10.0, 100.0, ("hrp",))
    with pytest.raises(ValueError, match="band thresholds"):
        BacktestingSettings(
            60,
            ("monthly",),
            10.0,
            100.0,
            ("equal_weight",),
            (0.0,),
        )
    with pytest.raises(ValueError, match="Band estimation"):
        BacktestingSettings(
            60,
            ("monthly",),
            10.0,
            100.0,
            ("equal_weight",),
            (0.05,),
            "weekly",
        )


@pytest.mark.parametrize(
    ("frequencies", "cost_bps", "initial_value", "strategies", "message"),
    [
        ((), 10.0, 100.0, ("equal_weight",), "At least one rebalance"),
        (("monthly", "monthly"), 10.0, 100.0, ("equal_weight",), "duplicated"),
        (("monthly",), -1.0, 100.0, ("equal_weight",), "basis points"),
        (("monthly",), 10.0, 0.0, ("equal_weight",), "initial value"),
        (("monthly",), 10.0, 100.0, (), "At least one backtest strategy"),
        (
            ("monthly",),
            10.0,
            100.0,
            ("equal_weight", "equal_weight"),
            "strategies cannot be duplicated",
        ),
    ],
)
def test_backtesting_settings_validate_duplicates_and_ranges(
    frequencies: tuple[str, ...],
    cost_bps: float,
    initial_value: float,
    strategies: tuple[str, ...],
    message: str,
) -> None:
    """Backtest configuration must reject ambiguous or invalid ranges."""
    with pytest.raises(ValueError, match=message):
        BacktestingSettings(
            60,
            frequencies,
            cost_bps,
            initial_value,
            strategies,
        )


def test_regime_and_robustness_settings_validate_research_controls() -> None:
    """Robustness settings must reject invalid ranges and overlapping regimes."""
    first = RegimeSettings(
        "first",
        "First",
        date(2020, 1, 1),
        date(2020, 6, 30),
    )
    overlap = RegimeSettings(
        "second",
        "Second",
        date(2020, 6, 30),
        date(2020, 12, 31),
    )
    with pytest.raises(ValueError, match="precede"):
        RegimeSettings("invalid", "Invalid", date(2021, 1, 1), date(2020, 1, 1))
    with pytest.raises(ValueError, match="cannot overlap"):
        RobustnessSettings(
            (0.0,),
            (60,),
            (0.5,),
            "quarterly",
            3,
            (first, overlap),
        )
    with pytest.raises(ValueError, match="cost scenarios"):
        RobustnessSettings((-1.0,), (60,), (0.5,), "quarterly", 3, (first,))
    with pytest.raises(ValueError, match="lookbacks"):
        RobustnessSettings((0.0,), (1,), (0.5,), "quarterly", 3, (first,))
    with pytest.raises(ValueError, match="maximum weights"):
        RobustnessSettings((0.0,), (60,), (0.0,), "quarterly", 3, (first,))


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (lambda: ProjectSettings("", "USD"), "name"),
        (lambda: ProjectSettings("Research", "US"), "currency"),
        (
            lambda: StudySettings(date(2020, 1, 2), date(2020, 1, 1), date(2020, 1, 1)),
            "end date",
        ),
        (
            lambda: StudySettings(date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 1)),
            "Out-of-sample",
        ),
        (lambda: DataSettings("other", "1d", "Adj Close", False), "only"),
        (lambda: DataSettings("yahoo_finance", "", "Adj Close", False), "frequency"),
        (lambda: DataSettings("yahoo_finance", "1d", "", False), "Price field"),
        (lambda: AssetDefinition("VTI", "", "us_equity", "Growth"), "name"),
        (lambda: BenchmarkConstituent("", 1.0), "ticker"),
        (lambda: BenchmarkConstituent("VT", 0.0), "weights"),
    ],
)
def test_domain_settings_reject_invalid_values(settings, message: str) -> None:  # type: ignore[no-untyped-def]
    """Invalid domain values must fail at the configuration boundary."""
    with pytest.raises(ValueError, match=message):
        settings()


def test_universe_requires_unique_tickers_and_sleeves() -> None:
    """Each initial economic sleeve must have one unique vehicle."""
    first = AssetDefinition("AAA", "Asset A", "equity", "Growth")
    same_ticker = AssetDefinition("AAA", "Asset B", "bonds", "Defense")
    same_sleeve = AssetDefinition("BBB", "Asset B", "equity", "Diversifier")

    with pytest.raises(ValueError, match="cannot be empty"):
        UniverseDefinition("saa", date(2026, 1, 1), "USD", (), ())
    with pytest.raises(ValueError, match="tickers"):
        UniverseDefinition("saa", date(2026, 1, 1), "USD", (first, same_ticker), ())
    with pytest.raises(ValueError, match="one ETF per sleeve"):
        UniverseDefinition("saa", date(2026, 1, 1), "USD", (first, same_sleeve), ())


def test_benchmark_requires_unique_nonempty_constituents() -> None:
    """The external benchmark definition must be unambiguous."""
    with pytest.raises(ValueError, match="cannot be empty"):
        BenchmarkDefinition("Empty", "Empty", "quarterly", (), "BIL")
    with pytest.raises(ValueError, match="cannot be duplicated"):
        BenchmarkDefinition(
            "Duplicate",
            "Duplicate",
            "quarterly",
            (BenchmarkConstituent("VT", 0.5), BenchmarkConstituent("VT", 0.5)),
            "BIL",
        )


def test_research_config_validates_currency_and_cash_hurdle() -> None:
    """Cross-file configuration relationships must be enforced."""
    config = load_research_config(PROJECT_ROOT / "configs")

    with pytest.raises(ValueError, match="currencies"):
        replace(config, project=replace(config.project, base_currency="EUR"))
    with pytest.raises(ValueError, match="cash hurdle"):
        replace(config, benchmark=replace(config.benchmark, cash_hurdle="CASH"))


def _copy_configs(tmp_path: Path) -> Path:
    target = tmp_path / "configs"
    shutil.copytree(PROJECT_ROOT / "configs", target)
    return target


def _update_yaml(path: Path, section: str, key: str, value: object) -> None:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload[section][key] = value
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


@pytest.mark.parametrize(
    ("section", "key", "value", "error_type", "message"),
    [
        ("data", "auto_adjust", "false", TypeError, "boolean"),
        ("study", "start_date", "not-a-date", ValueError, "YYYY-MM-DD"),
        ("paths", "raw", "../outside", ValueError, "project-relative"),
    ],
)
def test_loader_rejects_invalid_scalar_configuration(
    tmp_path: Path,
    section: str,
    key: str,
    value: object,
    error_type: type[Exception],
    message: str,
) -> None:
    """Malformed scalar YAML values must not reach the data provider."""
    config_dir = _copy_configs(tmp_path)
    _update_yaml(config_dir / "base.yaml", section, key, value)

    with pytest.raises(error_type, match=message):
        load_research_config(config_dir)


def test_loader_rejects_missing_and_malformed_files(tmp_path: Path) -> None:
    """Missing files and invalid YAML structures must fail explicitly."""
    config_dir = _copy_configs(tmp_path)
    (config_dir / "benchmark.yaml").unlink()
    with pytest.raises(FileNotFoundError, match="does not exist"):
        load_research_config(config_dir)

    config_dir = _copy_configs(tmp_path / "malformed")
    (config_dir / "universe.yaml").write_text("[]\n", encoding="utf-8")
    with pytest.raises(TypeError, match="must be a mapping"):
        load_research_config(config_dir)


def test_loader_rejects_invalid_lists_and_numbers(tmp_path: Path) -> None:
    """Container shape and benchmark weight types must be validated."""
    config_dir = _copy_configs(tmp_path)
    universe = yaml.safe_load((config_dir / "universe.yaml").read_text(encoding="utf-8"))
    universe["assets"] = "VTI"
    (config_dir / "universe.yaml").write_text(
        yaml.safe_dump(universe, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(TypeError, match="must be a list"):
        load_research_config(config_dir)

    config_dir = _copy_configs(tmp_path / "number")
    benchmark = yaml.safe_load((config_dir / "benchmark.yaml").read_text(encoding="utf-8"))
    benchmark["constituents"][0]["weight"] = True
    (config_dir / "benchmark.yaml").write_text(
        yaml.safe_dump(benchmark, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(TypeError, match="must be numeric"):
        load_research_config(config_dir)
