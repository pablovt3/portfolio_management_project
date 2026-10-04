"""Load the study's cached prices without silently requesting new market data."""

from pathlib import Path

import pandas as pd

from portfolio_management_project.config import ResearchConfig


def read_prices(config: ResearchConfig) -> pd.DataFrame:
    """Apply the declared sample boundary when reading the processed cache."""
    path: Path = config.paths.processed / "adjusted_close.csv"
    if not path.is_file():
        raise FileNotFoundError(f"No processed prices at {path}. Run scripts/build_data.py first.")
    prices = pd.read_csv(path, index_col=0, parse_dates=True)
    return prices.loc[
        (prices.index >= pd.Timestamp(config.study.start_date))
        & (prices.index < pd.Timestamp(config.study.end_date))
    ].copy()
