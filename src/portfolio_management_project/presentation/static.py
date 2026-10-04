"""Export research figures without requiring a browser process."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from portfolio_management_project.presentation.charts import COLORS, strategy_family
from portfolio_management_project.presentation.language import Language


def export_figures(data: Path, output: Path) -> None:
    """Make the four report figures directly from the published evidence."""
    output.mkdir(parents=True, exist_ok=True)
    language = Language(data.parents[1])
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#172D42",
            "text.color": "#172D42",
        }
    )
    wealth = pd.read_csv(data / "normalized_wealth.csv", index_col=0, parse_dates=True)
    scores = pd.read_csv(data / "strategy_scorecard.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(12, 7), layout="constrained")
    for name in dict.fromkeys([str(scores.index[0]), "equal_weight_quarterly", "benchmark_60_40"]):
        key = strategy_family(name)
        ax.plot(wealth.index, wealth[name], label=language.strategy(name), color=COLORS[key], lw=2)
    ax.set(title="Growth of 100 USD · net of rebalance costs", ylabel="Wealth (USD)")
    ax.legend(loc="upper left", frameon=False)
    ax.grid(alpha=0.15)
    fig.savefig(output / "strategy_wealth.png", dpi=150)
    plt.close(fig)

    frontier = pd.read_csv(data / "efficient_frontier.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(12, 7), layout="constrained")
    ax.plot(frontier.volatility * 100, frontier.expected_return * 100, color="#315BCB", lw=2)
    ax.set(
        title="Efficient frontier · full-sample diagnostic",
        xlabel="Expected annual volatility (%)",
        ylabel="Expected annual return (%)",
    )
    ax.grid(alpha=0.15)
    fig.savefig(output / "efficient_frontier.png", dpi=150)
    plt.close(fig)

    correlation = pd.read_csv(data / "correlations.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(10, 8), layout="constrained")
    heat = ax.imshow(correlation, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(correlation)), correlation.columns)
    ax.set_yticks(range(len(correlation)), correlation.index)
    ax.set_title("Historical return correlations", pad=20)
    for row in range(len(correlation)):
        for column in range(len(correlation)):
            value = correlation.iloc[row, column]
            ax.text(
                column,
                row,
                f"{value:.2f}",
                ha="center",
                va="center",
                color="white" if abs(value) > 0.65 else "#172D42",
            )
    fig.colorbar(heat, ax=ax, shrink=0.75)
    fig.savefig(output / "correlation_heatmap.png", dpi=150)
    plt.close(fig)

    performance = pd.read_csv(data / "strategy_performance.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(12, 8), layout="constrained")
    for name, row in performance.iterrows():
        key = strategy_family(str(name))
        ax.scatter(
            row.annualized_volatility * 100,
            row.annualized_return * 100,
            color=COLORS[key],
            marker="s" if str(name).endswith("monthly") else "o",
            label=language.strategy(str(name)),
            s=65,
        )
    ax.set(
        title="Realized risk and return · net of rebalance costs",
        xlabel="Annualized volatility (%)",
        ylabel="Compound annual growth (%)",
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=9)
    ax.grid(alpha=0.15)
    fig.savefig(output / "strategy_metrics.png", dpi=150)
    plt.close(fig)
