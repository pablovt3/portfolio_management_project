"""Rebuild the research from cached prices; no download is needed."""

import argparse
import logging
from pathlib import Path

from portfolio_management_project.research import run_study


def main() -> None:
    """Publish one coherent set of tables, charts and conclusions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-images", action="store_true", help="Skip PNG export")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    study = run_study(Path(__file__).resolve().parents[1], save_images=not args.no_images)
    print(f"Study ready: {study.publication.html_report}")


if __name__ == "__main__":
    main()
