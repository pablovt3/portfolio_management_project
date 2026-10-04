"""Build the governed market dataset and its reproducibility manifest."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from portfolio_management_project.config import load_research_config
from portfolio_management_project.pipelines import run_data_pipeline


def main() -> None:
    """Run the configured market-data pipeline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "configs",
        help="Directory containing base.yaml, universe.yaml, and benchmark.yaml.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    arguments = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_research_config(arguments.config_dir)
    result = run_data_pipeline(config)
    print(f"Manifest: {result.manifest_path}")
    print(f"Processed prices: {result.processed_prices_path}")
    print(f"Data quality: {result.quality_report_path}")


if __name__ == "__main__":
    main()
