"""Run the no-look-ahead walk-forward backtesting pipeline."""

from pathlib import Path

from portfolio_management_project.config import load_research_config
from portfolio_management_project.pipelines import run_backtesting_pipeline


def main() -> None:
    """Run configured strategies, frequencies, costs, and benchmark comparison."""
    root = Path(__file__).resolve().parents[1]
    config = load_research_config(root / "configs")
    result, exported = run_backtesting_pipeline(config)
    print(result.performance())
    if exported is not None:
        print(f"Summary: {exported.summary_path}")


if __name__ == "__main__":
    main()
