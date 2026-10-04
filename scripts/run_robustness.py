"""Run robustness, drawdown, concentration, regime, and scorecard analysis."""

from pathlib import Path

from portfolio_management_project.config import load_research_config
from portfolio_management_project.pipelines import run_robustness_pipeline


def main() -> None:
    """Execute and export the complete robustness specification."""
    root = Path(__file__).resolve().parents[1]
    config = load_research_config(root / "configs")
    result, exported = run_robustness_pipeline(config)
    print(result.scorecard[["balanced_rank_score", "overall_rank"]])
    if exported is not None:
        print(f"Summary: {exported.summary_path}")


if __name__ == "__main__":
    main()
