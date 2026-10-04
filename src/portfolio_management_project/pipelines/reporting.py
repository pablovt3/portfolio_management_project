"""Portfolio-ready reporting and publication artifact generation."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path

import pandas as pd
import plotly.io as pio

from portfolio_management_project.config import ResearchConfig
from portfolio_management_project.pipelines.backtesting import BacktestingResult
from portfolio_management_project.pipelines.construction import ConstructionResult
from portfolio_management_project.pipelines.eda import EDAResult
from portfolio_management_project.pipelines.robustness import RobustnessResult
from portfolio_management_project.presentation.charts import lines
from portfolio_management_project.presentation.language import Language

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportingResult:
    """Contain the public report, figures, data, and key findings."""

    report_directory: Path
    data_directory: Path
    figures_directory: Path
    markdown_report: Path
    html_report: Path
    key_findings: tuple[str, ...]


def build_publication_report(
    config: ResearchConfig,
    eda: EDAResult,
    construction: ConstructionResult,
    backtesting: BacktestingResult,
    robustness: RobustnessResult,
    *,
    save_images: bool = True,
) -> ReportingResult:
    """Build compact, versionable study artifacts for GitHub and the dashboard."""
    root = config.paths.artifacts.parent / "reports"
    data = root / "data"
    figures = root / "figures"
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    performance = backtesting.performance()
    trading = backtesting.comparison.trading_summary()
    relative = backtesting.comparison.benchmark_summary()
    wealth = backtesting.comparison.normalized_wealth()
    public_tables = {
        "strategy_performance": performance,
        "strategy_returns": backtesting.comparison.returns(),
        "cash_returns": backtesting.cash_returns.to_frame("BIL"),
        "allocation_audit": backtesting.allocation_audit,
        "decision_weights": pd.concat(
            {
                name: (
                    result.target_weights_history
                    if result.target_weights_history is not None
                    else result.weights_history
                ).loc[result.estimation_windows.index]
                for name, result in backtesting.strategies.items()
            },
            names=["strategy", "decision_date"],
        ),
        "benchmark_weights": backtesting.benchmark.weights_history,
        "strategy_trading": trading,
        "strategy_benchmark_metrics": relative,
        "strategy_scorecard": robustness.scorecard,
        "drawdown_summary": robustness.drawdown_summary,
        "drawdown_episodes": robustness.drawdown_episodes,
        "concentration_summary": robustness.concentration_summary,
        "regime_performance": robustness.regime_performance,
        "cost_sensitivity": robustness.cost_sensitivity,
        "lookback_sensitivity": robustness.lookback_sensitivity,
        "weight_cap_sensitivity": robustness.weight_cap_sensitivity,
        "normalized_wealth": wealth,
        "strategy_drawdowns": backtesting.comparison.drawdowns(),
        "construction_weights": construction.weights,
        "construction_ex_ante": construction.ex_ante_summary,
        "efficient_frontier": pd.DataFrame(
            {
                "expected_return": construction.frontier.expected_returns,
                "volatility": construction.frontier.volatilities,
                "sharpe_ratio": construction.frontier.sharpe_ratios,
            }
        ),
        "capital_allocation_line": pd.DataFrame(
            {
                "allocation": construction.capital_allocation_line.allocations,
                "risk_free_allocation": (
                    construction.capital_allocation_line.risk_free_allocations
                ),
                "expected_return": construction.capital_allocation_line.expected_returns,
                "volatility": construction.capital_allocation_line.volatilities,
            }
        ),
        "correlations": eda.correlations,
        "data_quality": eda.missing_values,
    }
    for name, table in public_tables.items():
        table.to_csv(data / f"{name}.csv", date_format="%Y-%m-%d")

    return refresh_publication(root, config, save_images=save_images)


def refresh_publication(
    root: Path,
    config: ResearchConfig,
    *,
    save_images: bool = True,
) -> ReportingResult:
    """Rebuild presentation from complete tables without rerunning optimizations."""
    data = root / "data"
    figures = root / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    performance = pd.read_csv(data / "strategy_performance.csv", index_col=0)
    scores = pd.read_csv(data / "strategy_scorecard.csv", index_col=0)
    sensitivity = pd.read_csv(data / "lookback_sensitivity.csv", index_col=[0, 1])
    wealth = pd.read_csv(data / "normalized_wealth.csv", index_col=0, parse_dates=True)
    findings = _key_findings_from_tables(performance, scores, sensitivity)
    language = Language(root.parent)
    leader = str(scores.index[0])
    chosen = list(dict.fromkeys([leader, "equal_weight_quarterly", "benchmark_60_40"]))
    wealth_chart = lines(wealth[chosen], language, "Growth of 100 USD")
    image_names = [
        "strategy_wealth",
        "efficient_frontier",
        "correlation_heatmap",
        "strategy_metrics",
    ]
    if save_images:
        from portfolio_management_project.presentation.static import export_figures

        export_figures(data, figures)

    snapshot = performance.loc[
        chosen, ["annualized_return", "annualized_volatility", "sharpe_ratio", "maximum_drawdown"]
    ].copy()
    snapshot.index = [language.strategy(str(name)) for name in snapshot.index]
    for column in snapshot:
        template = "{:.3f}" if column == "sharpe_ratio" else "{:.2%}"
        snapshot[column] = snapshot[column].map(template.format)
    snapshot.columns = [language.column(str(column)) for column in snapshot.columns]
    paragraphs = [
        "Does optimized allocation improve the balance of growth, risk and trading effort "
        "relative to a simple global policy? We compare five rules under calendar schedules "
        "and three drift-band policies.",
        "The reference is 60% VT / 40% BND, rebalanced quarterly. Both sides pay the same "
        f"{config.backtesting.transaction_cost_bps:g} bps on gross rebalance notional. Initial "
        "purchase costs are excluded for both. BIL is a separate dated cash reference for Sharpe.",
        "The scorecard averages eight ranks: CAGR, volatility, Sharpe, drawdown, Calmar, "
        "turnover, information ratio and average largest position. Several criteria overlap. "
        "The ranking is a declared preference, not a universal investor utility function.",
        "The window experiment shares a later calendar to accommodate its longest training "
        "period. Costs and position caps use the baseline calendar. Incomplete scenarios stay "
        "visible in the evidence rather than becoming zero returns.",
        "The sample is also used to identify the leaders. A separate holdout or a prospective "
        "paper portfolio is needed to test a selection rule. The universe is not fully "
        "point-in-time; taxes, market impact, variable spreads, liabilities and FX hedging "
        "remain outside this study.",
    ]
    bullets = "\n".join(f"- {item}" for item in findings)
    markdown = "# Global multi-asset research — executive note\n\n"
    markdown += f"Evaluation: {wealth.index.min():%Y-%m-%d} to {wealth.index.max():%Y-%m-%d}.\n\n"
    markdown += paragraphs[0] + "\n\n" + bullets + "\n\n"
    markdown += "## Benchmark and measurement\n\n" + paragraphs[1] + "\n\n"
    markdown += "Realized Sharpe uses the mean and sample deviation of daily excess returns "
    markdown += "over BIL, annualized at 252 observations. CAGR remains compound growth.\n\n"
    markdown += "## Decision framework\n\n" + paragraphs[2] + "\n\n"
    markdown += "## Compact strategy snapshot\n\n" + _markdown_table(snapshot) + "\n\n"
    markdown += "## Robustness and next step\n\n" + "\n\n".join(paragraphs[3:]) + "\n"
    markdown_path = root / "executive_summary.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    chart_html = pio.to_html(wealth_chart, full_html=False, include_plotlyjs=True)
    html_path = root / "executive_summary.html"
    html = """<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Global multi-asset research</title><style>
    body{font:17px/1.65 system-ui;color:#172D42;background:#F4F7FA;margin:0}
    main{max-width:1080px;margin:40px auto;background:white;padding:48px;border-radius:16px}
    h1{font-size:38px;line-height:1.2} h2{margin-top:40px} th,td{padding:12px;text-align:left}
    table{border-collapse:collapse;width:100%;font-size:14px}tr{border-bottom:1px solid #DCE4EA}
    .eyebrow{color:#188575;letter-spacing:.12em;font-size:12px}.chart{overflow:auto}
    @media(max-width:700px){main{margin:0;padding:22px}h1{font-size:28px}table{display:block;overflow:auto}}
    </style><main><p class="eyebrow">GLOBAL MULTI-ASSET · USD · RESEARCH NOTE</p>
    <h1>What does optimization add?</h1>"""
    html += f"<p>{escape(paragraphs[0])}</p><ul>"
    html += "".join(f"<li>{escape(item)}</li>" for item in findings) + "</ul>"
    html += '<div class="chart">' + chart_html + "</div>"
    html += "<h2>Benchmark and measurement</h2><p>" + escape(paragraphs[1]) + "</p>"
    html += "<h2>Decision framework</h2><p>" + escape(paragraphs[2]) + "</p>"
    html += "<h2>Compact strategy snapshot</h2>" + snapshot.to_html(border=0)
    html += "<h2>Robustness and next step</h2>" + "".join(
        f"<p>{escape(x)}</p>" for x in paragraphs[3:]
    )
    html_path.write_text(html + "</main></html>", encoding="utf-8")
    tables = sorted(path.stem for path in data.glob("*.csv"))
    manifest = {
        "schema_version": 2,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "config_digest": config.config_digest,
        "study_name": config.project.name,
        "out_of_sample_start": str(wealth.index.min().date()),
        "out_of_sample_end_exclusive": str(config.study.end_date),
        "strategies": list(scores.index),
        "benchmark": config.benchmark.name,
        "benchmark_cost_bps": config.backtesting.transaction_cost_bps,
        "sharpe_convention": "Annualized mean / sample deviation of daily returns in excess of BIL",
        "initial_purchase_cost": "Excluded for both strategies and benchmark",
        "public_tables": tables,
        "table_sha256": {
            name: hashlib.sha256((data / f"{name}.csv").read_bytes()).hexdigest() for name in tables
        },
        "static_figures": sorted(f"{name}.png" for name in image_names) if save_images else [],
    }
    (data / "study_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return ReportingResult(root, data, figures, markdown_path, html_path, findings)


def _strategy_label(name: str) -> str:
    """Keep a readable English name for existing report consumers."""
    return "Global 60/40" if name == "benchmark_60_40" else name.replace("_", " ").title()


def _key_findings_from_tables(
    performance: pd.DataFrame,
    scorecard: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> tuple[str, ...]:
    """Recalculate narrative facts whenever the evidence changes."""
    strategies = performance.drop(index="benchmark_60_40")
    growth = str(strategies.annualized_return.idxmax())
    sharpe = str(strategies.sharpe_ratio.idxmax())
    defensive = str(strategies.maximum_drawdown.idxmin())
    leader = str(scorecard.index[0])
    difference = float(
        performance.loc[leader, "annualized_return"]
        - performance.loc["benchmark_60_40", "annualized_return"]
    )
    return (
        f"{_strategy_label(leader)} leads the declared eight-criterion scorecard.",
        f"{_strategy_label(growth)} has the highest observed CAGR "
        f"({strategies.loc[growth, 'annualized_return']:.2%}).",
        f"{_strategy_label(sharpe)} has the highest realized cash-reference Sharpe "
        f"({strategies.loc[sharpe, 'sharpe_ratio']:.3f}).",
        f"{_strategy_label(defensive)} has the smallest maximum drawdown "
        f"({strategies.loc[defensive, 'maximum_drawdown']:.2%}).",
        f"The scorecard leader's CAGR differs from the net benchmark by "
        f"{difference * 100:+.2f} percentage points per year.",
        f"Incomplete window scenarios: {int((sensitivity.status != 'success').sum())}; "
        "inspect their recorded reasons before drawing a robustness conclusion.",
    )


def _markdown_table(frame: pd.DataFrame) -> str:
    """Format the small, already-labelled executive snapshot without extra dependencies."""
    header = ["Strategy", *map(str, frame.columns)]
    rows = [header, ["---"] * len(header)]
    rows.extend([[str(name), *map(str, row)] for name, row in frame.iterrows()])
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)
