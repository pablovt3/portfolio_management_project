"""One entry point for the study, shared by scripts and notebooks."""

from dataclasses import dataclass
from pathlib import Path

from portfolio_management_project.config import load_research_config
from portfolio_management_project.inputs import read_prices
from portfolio_management_project.pipelines import (
    BacktestingResult,
    ConstructionResult,
    EDAResult,
    ReportingResult,
    RobustnessResult,
    build_publication_report,
    run_backtesting_pipeline,
    run_construction_pipeline,
    run_eda_pipeline,
    run_robustness_pipeline,
)


@dataclass(frozen=True)
class Study:
    """Keep the evidence together so each output refers to the same run."""

    market: EDAResult
    construction: ConstructionResult
    backtest: BacktestingResult
    robustness: RobustnessResult
    publication: ReportingResult


def run_study(root: Path, *, save_images: bool = True) -> Study:
    """Read the cached prices once, then build and publish the research."""
    config = load_research_config(root / "configs")
    prices = read_prices(config)
    market, _ = run_eda_pipeline(config, prices=prices)
    construction, _ = run_construction_pipeline(config, prices=prices)
    backtest, _ = run_backtesting_pipeline(config, prices=prices)
    robustness, _ = run_robustness_pipeline(config, prices=prices, baseline=backtest)
    publication = build_publication_report(
        config,
        market,
        construction,
        backtest,
        robustness,
        save_images=save_images,
    )
    return Study(market, construction, backtest, robustness, publication)
