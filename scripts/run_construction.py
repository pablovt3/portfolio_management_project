"""Run the static classical portfolio-construction pipeline."""

from pathlib import Path

from portfolio_management_project.config import load_research_config
from portfolio_management_project.pipelines import run_construction_pipeline


def main() -> None:
    """Run all currently supported classical construction models."""
    root = Path(__file__).resolve().parents[1]
    config = load_research_config(root / "configs")
    result, exported = run_construction_pipeline(config)
    print(result.ex_ante_summary[["expected_return", "volatility", "sharpe_ratio"]])
    if exported is not None:
        print(f"Summary: {exported.summary_path}")


if __name__ == "__main__":
    main()
