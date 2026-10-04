"""One table formatter for notebooks and the dashboard."""

from __future__ import annotations

import pandas as pd
from pandas.io.formats.style import Styler

from portfolio_management_project.presentation.language import Language


def show_table(frame: pd.DataFrame, text: Language, *, strategies: bool = False) -> Styler:
    """Translate labels and format units without changing numerical evidence."""
    view = frame.copy()
    if strategies:
        view.index = [text.strategy(str(name)) for name in view.index]
        view.index.name = text("Strategy")
    elif isinstance(view.index, pd.MultiIndex):
        arrays = []
        for level, name in enumerate(view.index.names):
            values = view.index.get_level_values(level)
            arrays.append(
                [text.strategy(str(value)) for value in values] if name == "strategy" else values
            )
        view.index = pd.MultiIndex.from_arrays(arrays, names=view.index.names)
    view.index.names = [text.column(str(name)) if name else None for name in view.index.names]
    for column in view.columns:
        if pd.api.types.is_string_dtype(view[column]):
            translate = text.strategy if column == "strategy" else text
            view[column] = view[column].map(
                lambda value, translate=translate: (
                    translate(value) if isinstance(value, str) else value
                ),
            )
    percentages = {
        "annualized_return",
        "annualized_volatility",
        "maximum_drawdown",
        "expected_return",
        "volatility",
        "depth",
        "average_max_weight",
        "requested_target",
        "effective_target",
        "feasible_minimum",
        "feasible_maximum",
        "tracking_error",
        "transaction_cost_rate",
        "missing_fraction",
        "total_return",
    }
    counts = {
        "number_of_rebalances",
        "duration_days",
        "recovery_days",
        "observations",
        "lookback_periods",
        "overall_rank",
        "missing_observations",
        "number_of_assets",
    }
    formats = {}
    for name in view.select_dtypes(include="number").columns:
        template = "{:.2%}" if name in percentages else "{:.0f}" if name in counts else "{:.3f}"
        formats[text.column(str(name))] = template
    view.columns = [text.column(str(name)) for name in view.columns]
    return view.style.format(formats, na_rep="—")
