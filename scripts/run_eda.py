"""Run the library-driven exploratory data analysis pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from portfolio_management_project.config import load_research_config
from portfolio_management_project.pipelines import run_eda_pipeline


def main() -> None:
    """Run EDA from the processed governed price matrix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "configs",
    )
    arguments = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_research_config(arguments.config_dir)
    result, exported = run_eda_pipeline(config)
    print(f"Assets analyzed: {len(result.prices.columns)}")
    if exported is not None:
        print(f"EDA summary: {exported.summary_path}")
        print(f"Tables: {exported.tables_directory}")
        print(f"Figures: {exported.figures_directory}")


if __name__ == "__main__":
    main()
