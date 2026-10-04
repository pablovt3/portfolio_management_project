"""Explain the experiment, then let readers inspect its evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from portfolio_management_project.presentation.charts import (
    COLORS,
    allocations,
    finish,
    lines,
    strategy_family,
)
from portfolio_management_project.presentation.evidence import Evidence
from portfolio_management_project.presentation.language import Language
from portfolio_management_project.presentation.notebook import show_table

PAGES = (
    "Research overview",
    "How the study works",
    "Rebalancing policies",
    "Investment universe",
    "The benchmark",
    "Portfolio construction",
    "Out-of-sample results",
    "Risk and drawdowns",
    "Strategy comparison",
    "Robustness",
    "Conclusions",
    "Downloads",
)


def main() -> None:
    """Choose the language once; both versions share every page and calculation."""
    root = Path(__file__).resolve().parents[3]
    st.set_page_config(page_title="Portfolio Research", page_icon="◈", layout="wide")
    available = ["en"] + (["es"] if (root / "locales/es.json").is_file() else [])
    code = st.sidebar.selectbox(
        "Language / Idioma" if len(available) > 1 else "Language",
        available,
        format_func=lambda x: "English" if x == "en" else "Español",
    )
    text = Language(root, code)
    st.markdown(
        """<style>
    .block-container {max-width: 1320px; padding-top: 2.5rem; padding-bottom: 4rem;}
    [data-testid="stMetric"] {border: 1px solid #DCE4EA; border-radius: 12px; padding: 16px;}
    [data-testid="stMetricValue"] {font-size: 1.8rem;}
    </style>""",
        unsafe_allow_html=True,
    )
    st.sidebar.title(text("Portfolio Research"))
    page = st.sidebar.radio(text("Explore the study"), PAGES, format_func=text)
    st.sidebar.caption(text("A data-driven study of allocation, risk and implementation."))
    try:
        evidence = Evidence(root)
    except (FileNotFoundError, ValueError) as error:
        st.error(text("Published evidence is unavailable or outdated. Rebuild the study."))
        st.code("python scripts/run_study.py")
        st.caption(str(error))
        return
    st.caption(text("GLOBAL MULTI-ASSET · USD · RESEARCH NOTE"))
    st.title(text(page))
    renderers = dict(
        zip(
            PAGES,
            (
                overview,
                methodology,
                rebalancing,
                universe,
                benchmark,
                construction,
                backtesting,
                risk,
                comparison,
                robustness,
                conclusions,
                downloads,
            ),
            strict=True,
        )
    )
    renderers[page](evidence, text)
    st.divider()
    st.caption(
        text(
            "Historical research, not a forecast. ETF selection reflects present-day availability."
        )
    )


def table(
    frame: pd.DataFrame,
    text: Language,
    *,
    strategies: bool = False,
    width: Literal["stretch", "content"] | int = "stretch",
) -> None:
    """Use the same readable financial tables as the research notebook."""
    st.dataframe(show_table(frame, text, strategies=strategies), width=width)


def chart(figure: go.Figure) -> None:
    st.plotly_chart(figure, width="stretch")


def period(frame: pd.DataFrame, text: Language) -> None:
    st.caption(
        f"{text('Evaluation period')}: {frame.index.min():%Y-%m-%d} → {frame.index.max():%Y-%m-%d}"
    )


def metrics(row: pd.Series, text: Language) -> None:
    for box, key in zip(
        st.columns(4),
        ("annualized_return", "annualized_volatility", "sharpe_ratio", "maximum_drawdown"),
        strict=True,
    ):
        value = float(row[key])
        box.metric(text.column(key), f"{value:.2f}" if key == "sharpe_ratio" else f"{value:.2%}")


def overview(evidence: Evidence, text: Language) -> None:
    st.markdown(
        text(
            "Does a more sophisticated allocation rule improve the outcome after risk "
            "and trading costs?"
        )
    )
    st.write(
        text(
            "We compare five portfolio rules using nine ETFs. Targets are estimated "
            "from the previous three years and implemented with calendar schedules or "
            "drift bands. The 60/40 benchmark gives us a simple external reference."
        )
    )
    wealth = evidence.dates("normalized_wealth")
    period(wealth, text)
    performance = evidence.table("strategy_performance")
    selected = st.selectbox(
        text("Inspect a strategy"),
        performance.index,
        format_func=text.strategy,
        index=list(performance.index).index("target_return_quarterly"),
    )
    metrics(performance.loc[selected], text)
    chart(
        lines(wealth[list(dict.fromkeys([selected, "benchmark_60_40"]))], text, "Growth of 100 USD")
    )
    st.info(
        text(
            "Read the benchmark first, then compare net performance, drawdowns and "
            "robustness. A higher return alone does not make a strategy better."
        )
    )
    st.caption(
        text(
            "Sharpe uses daily excess returns over BIL. Trading costs apply to both "
            "strategies and benchmark; initial purchases are excluded for both."
        )
    )


def methodology(evidence: Evidence, text: Language) -> None:
    """Connect the data, decisions, trading rules and evaluation in one page."""
    config = evidence.config
    st.write(
        text(
            "The project simulates a repeatable investment process. It does not choose "
            "one portfolio with knowledge of the complete future. At every decision date, "
            "it estimates the models using only information that was already available."
        )
    )

    st.subheader(text("One decision cycle"))
    steps = (
        ("1 · Observe", "Read the nine ETF prices available before the decision."),
        (
            "2 · Estimate",
            "Use the previous 756 daily returns, approximately three trading years.",
        ),
        (
            "3 · Allocate",
            "Calculate target weights with each of the five portfolio rules.",
        ),
        (
            "4 · Rebalance",
            "Trade on a calendar date or after a weight crosses its drift band, then deduct costs.",
        ),
        (
            "5 · Evaluate",
            "Apply subsequent returns, then measure growth, risk, losses and turnover.",
        ),
    )
    for column, (heading, explanation) in zip(st.columns(5), steps, strict=True):
        with column:
            st.markdown(f"**{text(heading)}**")
            st.caption(text(explanation))

    st.subheader(text("What is compared"))
    st.write(
        text(
            "Each allocation rule has monthly and quarterly calendar versions plus three "
            "drift-band versions at ±2.5, ±5 and ±7.5 percentage points. This produces "
            "25 strategy variants. The external benchmark is 60% VT and 40% BND and "
            "rebalances quarterly."
        )
    )
    strategy_rows = [
        {
            "Strategy": text.strategy(strategy),
            "Purpose": text(purpose),
        }
        for strategy, purpose in (
            ("equal_weight", "Simple allocation with the same target weight in every ETF."),
            ("minimum_variance", "Seek the lowest estimated portfolio volatility."),
            ("mean_variance", "Balance estimated return against estimated risk."),
            ("target_return", "Seek the lowest risk for a feasible return objective."),
            ("maximum_sharpe", "Seek the highest estimated excess return per unit of risk."),
        )
    ]
    table(pd.DataFrame(strategy_rows), text, width=900)

    left, right = st.columns(2)
    with left:
        st.subheader(text("Rebalancing"))
        st.write(
            text(
                "Calendar policies include monthly rebalancing, which reconsiders targets "
                "about twelve times per year; quarterly rebalancing does so about four "
                "times. Between decisions, holdings "
                "drift as market prices change. More frequent decisions can adapt sooner, "
                "but they can also create more turnover. Band versions re-estimate targets "
                "monthly and trade only after at least one asset breaches its band."
            )
        )
    with right:
        st.subheader(text("Transaction costs"))
        cost_bps = config.backtesting.transaction_cost_bps
        st.metric(text("Baseline cost"), f"{cost_bps:g} bps = {cost_bps / 100:.2f}%")
        st.write(
            text(
                "The cost is charged on the gross amount traded at every rebalance. If 20% "
                "of a USD 100 portfolio is traded with a 0.10% rate, the deduction is USD "
                "0.02. Initial purchases are excluded for both strategies and benchmark."
            )
        )

    st.subheader(text("How performance is judged"))
    measures = pd.DataFrame(
        [
            {
                "Measure": text("CAGR"),
                "Question": text("How quickly did wealth compound?"),
            },
            {
                "Measure": text("Volatility"),
                "Question": text("How variable were daily returns?"),
            },
            {
                "Measure": text("Sharpe vs BIL"),
                "Question": text("How much excess return was earned per unit of variability?"),
            },
            {
                "Measure": text("Maximum drawdown"),
                "Question": text("What was the deepest loss from a previous peak?"),
            },
            {
                "Measure": text("Turnover and cost"),
                "Question": text("How much trading did implementation require?"),
            },
        ]
    )
    table(measures, text, width=900)
    st.info(
        text(
            "The static efficient frontier uses the complete sample only to explain the "
            "models. Strategy performance comes from the lagged walk-forward simulation. "
            "That separation is essential: an explanatory portfolio is not a historical "
            "portfolio that could actually have been held."
        )
    )


def universe(evidence: Evidence, text: Language) -> None:
    st.write(
        text(
            "Each ETF plays a role in the portfolio. Diversification depends on their "
            "joint behavior, not on the number of tickers."
        )
    )
    assets = evidence.config.universe.assets
    table(
        pd.DataFrame([{"Ticker": a.ticker, "Name": a.name, "Role": a.role} for a in assets]), text
    )
    correlations = evidence.table("correlations")
    figure = px.imshow(
        correlations, zmin=-1, zmax=1, color_continuous_scale="RdBu_r", text_auto=".2f"
    )
    finish(figure, text("Historical return correlations"), height=520)
    figure.update_layout(
        hovermode="closest",
        margin={"l": 55, "r": 30, "t": 65, "b": 35},
    )
    chart(figure)
    st.caption(
        text(
            "Full-history diagnostic. Correlation can rise during stress and does not "
            "measure every source of risk."
        )
    )
    with st.expander(text("Data quality and provenance")):
        table(evidence.table("data_quality"), text, width=760)
        st.write(
            text(
                "Source: Yahoo Finance adjusted closing prices. Returns include "
                "adjustments for distributions and splits; data revisions remain "
                "possible."
            )
        )
        st.caption(f"{text('Published')}: {evidence.manifest['generated_at_utc']}")


def rebalancing(evidence: Evidence, text: Language) -> None:
    """Explain and compare calendar schedules with drift-triggered execution."""
    st.write(
        text(
            "A drift band separates target estimation from trade execution. Targets are "
            "re-estimated monthly. On every valuation date, the current pre-trade weights "
            "are compared with the latest target. A trade occurs only when at least one "
            "absolute deviation exceeds the selected band."
        )
    )
    st.info(
        text(
            "A ±5 percentage-point band means a 20% target may drift from 15% to 25%. "
            "Crossing either boundary triggers a full rebalance to the latest target. "
            "It does not mean a 5% relative change in the asset price."
        )
    )
    model = st.selectbox(
        text("Portfolio rule"),
        [
            "equal_weight",
            "minimum_variance",
            "mean_variance",
            "target_return",
            "maximum_sharpe",
        ],
        format_func=text.strategy,
    )
    policies = [
        f"{model}_monthly",
        f"{model}_quarterly",
        f"{model}_band_250bp",
        f"{model}_band_500bp",
        f"{model}_band_750bp",
    ]
    performance = evidence.table("strategy_performance").loc[policies]
    trading = evidence.table("strategy_trading").loc[policies]
    comparison = performance[
        ["annualized_return", "annualized_volatility", "sharpe_ratio", "maximum_drawdown"]
    ].join(
        trading[["number_of_rebalances", "total_turnover", "total_transaction_cost"]]
    )
    table(comparison, text, strategies=True)
    wealth = evidence.dates("normalized_wealth")
    chart(lines(wealth[policies], text, "Growth by rebalancing policy"))
    st.caption(
        text(
            "The three thresholds are declared research scenarios, not fitted optimal "
            "values. A narrower band usually reacts sooner and trades more; a wider band "
            "usually tolerates more drift. Compare the net result and trading burden "
            "before choosing a policy."
        )
    )
def benchmark(evidence: Evidence, text: Language) -> None:
    st.write(
        text(
            "The benchmark answers a practical question: what would a simple global "
            "stock-and-bond policy have delivered over the same dates?"
        )
    )
    parts = evidence.config.benchmark.constituents
    left, right = st.columns([1, 1.4])
    with left:
        figure = go.Figure(
            go.Pie(
                labels=[item.ticker for item in parts],
                values=[item.weight for item in parts],
                hole=0.68,
                marker_colors=["#315BCB", "#188575"],
                textinfo="label+percent",
            )
        )
        chart(finish(figure, text("Policy weights"), height=330))
    with right:
        st.subheader(text("What the two sleeves represent"))
        st.write(
            text(
                "VT provides global equity exposure. BND provides broad US "
                "investment-grade bond exposure. Their roles are growth and nominal "
                "income/defense, respectively."
            )
        )
        st.write(
            text(
                "At each quarterly rebalance, the portfolio returns to 60% VT and 40% "
                "BND. Between those dates the weights drift with market prices. It is "
                "not a daily constant-weight index."
            )
        )
        st.write(
            text(
                "This is an external policy benchmark. It uses different instruments "
                "and can hold 60% in one ETF, whereas optimized portfolios have a 35% "
                "per-ETF cap. It is not an equal-constraint optimization contest."
            )
        )
    wealth = evidence.dates("normalized_wealth")
    period(wealth, text)
    metrics(evidence.table("strategy_performance").loc["benchmark_60_40"], text)
    chart(lines(wealth[["benchmark_60_40"]], text, "Growth of 100 USD"))
    st.subheader(text("Costs and cash reference"))
    st.write(
        text(
            "Both sides pay the configured cost on gross traded notional at "
            "rebalancing. The baseline is 10 basis points (0.10%). Neither side "
            "includes an initial purchase charge, taxes or market impact."
        )
    )
    st.write(
        text(
            "BIL is the cash reference used for realized Sharpe ratios. It is separate "
            "from the 60/40 performance benchmark and remains an ETF proxy with small "
            "price movements and expenses."
        )
    )
    table(
        evidence.table("strategy_trading").loc[
            ["benchmark_60_40"],
            ["number_of_rebalances", "total_turnover", "total_transaction_cost"],
        ],
        text,
        strategies=True,
    )
    chart(allocations(evidence.dates("benchmark_weights"), text, history=True))
    st.caption(
        text(
            "Benchmark weights shown here are daily holdings after market drift and any rebalance."
        )
    )


def construction(evidence: Evidence, text: Language) -> None:
    st.warning(
        text(
            "These allocations and the frontier use the full estimation sample. They "
            "explain the models; they are not tradable historical results."
        )
    )
    st.write(
        text(
            "Equal weight is the simple baseline. Minimum variance emphasizes "
            "stability. Mean–variance trades expected return against risk. Target "
            "return seeks the least risk for a return objective. Maximum Sharpe seeks "
            "the strongest estimated excess return per unit of risk."
        )
    )
    chart(allocations(evidence.table("construction_weights").T, text))
    frontier = evidence.table("efficient_frontier")
    points = evidence.table("construction_ex_ante")
    figure = go.Figure(
        go.Scatter(
            x=frontier.volatility,
            y=frontier.expected_return,
            mode="lines",
            name=text("Efficient frontier"),
            line_color="#315BCB",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=points.volatility,
            y=points.expected_return,
            mode="markers",
            text=[text.strategy(str(x)) for x in points.index],
            name=text("Models"),
            marker={"size": 12, "color": "#188575"},
            hovertemplate="%{text}<br>%{x:.2%} · %{y:.2%}<extra></extra>",
        )
    )
    figure.update_xaxes(title=text("Expected volatility"), tickformat=".0%")
    figure.update_yaxes(title=text("Expected return"), tickformat=".0%")
    chart(finish(figure, text("Efficient frontier")))
    st.caption(
        text(
            "Expected returns are historical estimates, not forecasts. Covariance uses "
            "Ledoit–Wolf shrinkage. Portfolios are long-only, fully invested and capped "
            "at 35% per ETF."
        )
    )
    st.subheader(text("When the return target is not feasible"))
    st.write(
        text(
            "The 7% objective is clipped to the feasible range at each decision. The "
            "audit below shows when the requested target changed; 7% is never a "
            "promised realized return."
        )
    )
    audit = evidence.table("allocation_audit")
    adjusted = audit.loc[audit.target_adjusted]
    st.caption(f"{text('Adjusted decisions')}: {len(adjusted)} / {len(audit)}")
    table(adjusted, text)


def backtesting(evidence: Evidence, text: Language) -> None:
    st.write(
        text(
            "At each decision, estimation ends on the previous trading day. The "
            "portfolio is implemented at the decision-day close and earns subsequent "
            "returns. This timing keeps future observations out of the allocation."
        )
    )
    wealth = evidence.dates("normalized_wealth")
    period(wealth, text)
    chosen = st.multiselect(
        text("Strategies"),
        list(wealth.columns),
        default=["equal_weight_quarterly", "target_return_quarterly", "benchmark_60_40"],
        format_func=text.strategy,
    )
    if not chosen:
        st.info(text("Select at least one strategy to see the comparison."))
        return
    chart(lines(wealth[chosen], text, "Growth of 100 USD"))
    table(evidence.table("strategy_performance").loc[chosen], text, strategies=True)
    st.subheader(text("How the allocation changed"))
    weights = evidence.table("decision_weights", 2)
    selected = st.selectbox(
        text("Allocation history"),
        weights.index.get_level_values(0).unique(),
        format_func=text.strategy,
    )
    history = weights.loc[selected]
    history.index = pd.to_datetime(history.index)
    chart(allocations(history, text, history=True))
    st.caption(
        text(
            "These are target weights at decision dates, held as a step chart. Actual "
            "holdings drift between rebalances."
        )
    )
    table(
        evidence.table("strategy_trading").loc[
            chosen, ["number_of_rebalances", "total_turnover", "total_transaction_cost"]
        ],
        text,
        strategies=True,
    )


def risk(evidence: Evidence, text: Language) -> None:
    st.write(
        text(
            "A drawdown is the loss from a previous wealth peak. Its depth and recovery "
            "time describe an experience that annual volatility alone cannot capture."
        )
    )
    drawdowns = evidence.dates("strategy_drawdowns")
    selected = st.selectbox(text("Strategy"), drawdowns.columns, format_func=text.strategy)
    chart(
        lines(
            drawdowns[list(dict.fromkeys([selected, "benchmark_60_40"]))],
            text,
            "Underwater performance",
            percent=True,
        )
    )
    table(evidence.table("drawdown_episodes", 2).loc[selected], text)
    st.caption(
        text(
            "Drawdown charts show negative losses; tables report positive loss "
            "magnitudes. A missing recovery date means the episode was still open at "
            "the sample end. Durations are calendar days."
        )
    )


def comparison(evidence: Evidence, text: Language) -> None:
    performance = evidence.table("strategy_performance")
    figure = go.Figure()
    for name, row in performance.iterrows():
        figure.add_trace(
            go.Scatter(
                x=[row.annualized_volatility],
                y=[row.annualized_return],
                mode="markers",
                name=text.strategy(str(name)),
                marker={
                    "size": 12,
                    "color": COLORS[strategy_family(str(name))],
                },
                hovertemplate="%{x:.2%} · %{y:.2%}<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_xaxes(title=text("Annualized volatility"), tickformat=".0%")
    figure.update_yaxes(title=text("Annualized return (CAGR)"), tickformat=".0%")
    chart(finish(figure, text("Realized risk and return"), height=520))
    st.write(
        text(
            "The scorecard averages eight ranks: CAGR, volatility, Sharpe, drawdown, "
            "Calmar, turnover, information ratio and average largest position. Lower "
            "average rank is better. Numerical ties use a ten-decimal tolerance."
        )
    )
    st.info(
        text(
            "Several criteria overlap. Equal indicator weights do not imply equal "
            "economic importance. The ranking describes this sample and is not an "
            "independently validated selection rule."
        )
    )
    scores = evidence.table("strategy_scorecard")
    table(
        scores[
            [
                "overall_rank",
                "balanced_rank_score",
                "annualized_return",
                "sharpe_ratio",
                "maximum_drawdown",
                "total_turnover",
            ]
        ],
        text,
        strategies=True,
    )
    with st.expander(text("All criteria and benchmark-relative evidence")):
        table(scores, text, strategies=True)
        table(evidence.table("strategy_benchmark_metrics"), text, strategies=True)


def robustness(evidence: Evidence, text: Language) -> None:
    st.write(
        text(
            "Change one assumption at a time and check whether the interpretation "
            "survives. These are calculated historical scenarios, not live forecasts."
        )
    )
    scenario = st.selectbox(
        text("Scenario family"),
        ["Costs", "Estimation windows", "Position limits", "Market regimes"],
        format_func=text,
    )
    choices = {
        "Costs": ("cost_sensitivity", "cost_bps"),
        "Estimation windows": ("lookback_sensitivity", "lookback_periods"),
        "Position limits": ("weight_cap_sensitivity", "max_weight"),
        "Market regimes": ("regime_performance", "regime"),
    }
    name, variable = choices[scenario]
    frame = evidence.table(name, 2).reset_index()
    if "start_date" in frame:
        start = frame.start_date.dropna().min()
        end = frame.end_date.dropna().max()
        st.caption(f"{text('Evaluation dates')}: {start} → {end}")
    if scenario == "Estimation windows":
        st.info(
            text(
                "All window scenarios share the later start needed for five years of "
                "training. Compare windows with each other, not directly with the "
                "longer baseline period."
            )
        )
    if scenario == "Market regimes":
        selected = st.selectbox(
            text("Market regime"),
            frame.regime.unique(),
            format_func=lambda x: text(x.replace("_", " ").capitalize()),
        )
        table(frame[frame.regime == selected].drop(columns=["regime", "regime_label"]), text)
        return
    strategy = st.selectbox(text("Strategy"), frame.strategy.unique(), format_func=text.strategy)
    metric = st.selectbox(
        text("Metric"),
        ["annualized_return", "sharpe_ratio", "maximum_drawdown"],
        format_func=text.column,
    )
    selected = frame[frame.strategy == strategy]
    if "status" in selected and (selected.status != "success").any():
        st.warning(
            text(
                "Some scenarios could not be completed. Missing points are failures, "
                "not zero returns; inspect the status and reason below."
            )
        )
    figure = go.Figure(
        go.Scatter(
            x=selected[variable],
            y=selected[metric],
            mode="lines+markers",
            connectgaps=False,
            line_color="#315BCB",
            name=text.strategy(strategy),
        )
    )
    figure.update_xaxes(
        title=text.column(variable), tickformat=".0%" if variable == "max_weight" else None
    )
    figure.update_yaxes(
        title=text.column(metric), tickformat=None if metric == "sharpe_ratio" else ".1%"
    )
    chart(finish(figure, text.column(metric)))
    columns = [
        variable,
        "status",
        "error",
        "annualized_return",
        "sharpe_ratio",
        "maximum_drawdown",
        "total_turnover",
    ]
    table(selected[[x for x in columns if x in selected]], text)


def conclusions(evidence: Evidence, text: Language) -> None:
    scores = evidence.table("strategy_scorecard")
    performance = evidence.table("strategy_performance")
    strategies = performance.drop(index="benchmark_60_40")
    leader = str(scores.index[0])
    st.subheader(text("What the evidence supports"))
    st.write(
        text("The leading scorecard result is")
        + f" **{text.strategy(leader)}**. "
        + text("Its appeal comes from the combination of outcomes, not from winning every measure.")
    )
    table(performance.loc[[leader, "benchmark_60_40"]], text, strategies=True)
    priorities = {
        "Highest observed growth": strategies.annualized_return.idxmax(),
        "Highest realized Sharpe": strategies.sharpe_ratio.idxmax(),
        "Smallest drawdown": strategies.maximum_drawdown.idxmin(),
        "Lowest trading burden": evidence.table("strategy_trading")
        .drop(index="benchmark_60_40")
        .total_turnover.idxmin(),
    }
    table(pd.DataFrame({"Priority": list(priorities), "strategy": list(priorities.values())}), text)
    st.subheader(text("What remains uncertain"))
    st.write(
        text(
            "The same historical sample is used to inspect and rank strategies. This is "
            "useful research evidence, but selecting a winner afterwards does not "
            "establish future superiority. A separate holdout or prospective paper "
            "portfolio is the next validation step."
        )
    )
    st.write(
        text(
            "Results depend on ETF selection, USD denomination, historical estimates "
            "and a simple linear cost model. Taxes, market impact, changing spreads, "
            "liabilities and currency hedging are outside the experiment."
        )
    )
    st.caption(
        text(
            "The practical decision is a trade-off between growth, loss tolerance and "
            "implementation effort. Keep the benchmark visible when discussing any "
            "improvement."
        )
    )


def downloads(evidence: Evidence, text: Language) -> None:
    st.write(
        text(
            "Download the evidence behind the charts. Files keep stable English field "
            "names so they can be used in either language."
        )
    )
    name = st.selectbox(
        text("Evidence table"), evidence.manifest["public_tables"], format_func=text.column
    )
    st.download_button(
        text("Download CSV"),
        (evidence.directory / f"{name}.csv").read_bytes(),
        file_name=f"{name}.csv",
        mime="text/csv",
    )
