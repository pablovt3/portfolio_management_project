"""Consistent chart design for exploring the published research."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from portfolio_management_project.presentation.language import Language

COLORS = {
    "equal_weight": "#54738C",
    "minimum_variance": "#188575",
    "mean_variance": "#C47A35",
    "target_return": "#315BCB",
    "maximum_sharpe": "#9853A1",
    "benchmark_60_40": "#172D42",
}


def strategy_family(name: str) -> str:
    """Return the allocation model independent of its execution policy."""
    if name == "benchmark_60_40":
        return name
    for suffix in ("_monthly", "_quarterly"):
        if name.endswith(suffix):
            return name.removesuffix(suffix)
    if "_band_" in name:
        return name.split("_band_", maxsplit=1)[0]
    return name
ASSET_COLORS = [
    "#315BCB",
    "#7895E0",
    "#B0C2ED",
    "#188575",
    "#6BAEA0",
    "#A5CDC2",
    "#C47A35",
    "#DFBE63",
    "#9AA9B5",
]


def finish(figure: go.Figure, title: str = "", *, height: int = 450) -> go.Figure:
    """Give titles and legends their own space, including in saved figures."""
    figure.update_layout(
        title=title,
        template="plotly_white",
        height=height,
        font={"family": "Arial, sans-serif", "size": 13, "color": "#172D42"},
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin={"l": 55, "r": 30, "t": 65, "b": 100},
        legend={"orientation": "h", "y": -0.22, "x": 0},
        hovermode="x unified",
    )
    return figure


def lines(
    frame: pd.DataFrame, language: Language, title: str, *, percent: bool = False
) -> go.Figure:
    """Keep each strategy's color and rebalance-frequency style across all views."""
    figure = go.Figure()
    for name in frame.columns:
        key = strategy_family(str(name))
        figure.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[name],
                name=language.strategy(str(name)),
                mode="lines",
                line={
                    "color": COLORS.get(key, "#54738C"),
                    "width": 3 if name == "benchmark_60_40" else 2,
                    "dash": (
                        "dash"
                        if "_band_" in str(name)
                        else "dot" if str(name).endswith("_monthly") else "solid"
                    ),
                },
                hovertemplate=("%{y:.2%}" if percent else "%{y:.2f}")
                + "<extra>%{fullData.name}</extra>",
            )
        )
    if percent:
        figure.update_yaxes(tickformat=".0%")
    return finish(figure, language(title))


def allocations(weights: pd.DataFrame, language: Language, *, history: bool = False) -> go.Figure:
    """Show model weights or dated decision weights with stable asset colors."""
    figure = go.Figure()
    for index, asset in enumerate(weights.columns):
        color = ASSET_COLORS[index % len(ASSET_COLORS)]
        if history:
            trace = go.Scatter(
                x=weights.index,
                y=weights[asset],
                name=str(asset),
                stackgroup="one",
                mode="lines",
                line={"color": color, "shape": "hv"},
            )
        else:
            trace = go.Bar(
                x=[language.strategy(str(i)) for i in weights.index],
                y=weights[asset],
                name=str(asset),
                marker_color=color,
            )
        figure.add_trace(trace)
    figure.update_layout(barmode="stack")
    figure.update_yaxes(tickformat=".0%", range=[0, 1])
    return finish(figure, language("Decision weights" if history else "Static allocations"))
