"""Exercise the reader's journey in both available language editions."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from portfolio_management_project.presentation.dashboard import PAGES

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("page", PAGES)
def test_every_research_page_renders(page: str) -> None:
    app = AppTest.from_file(ROOT / "dashboard/app.py").run(timeout=30)
    app.sidebar.radio[0].set_value(page).run(timeout=30)
    assert not app.exception
    assert app.title[0].value == page
    assert "Configuration" not in app.sidebar.radio[0].options


def test_benchmark_explains_costs_and_cash_separately() -> None:
    app = AppTest.from_file(ROOT / "dashboard/app.py").run(timeout=30)
    app.sidebar.radio[0].set_value("The benchmark").run(timeout=30)
    prose = " ".join(element.value for element in [*app.markdown, *app.caption])
    assert "BIL" in prose and "VT" in prose and "BND" in prose
    assert "gross traded notional" in prose
    assert len(app.metric) == 4
    assert len(app.get("plotly_chart")) == 3


def test_methodology_connects_estimation_rebalancing_and_costs() -> None:
    app = AppTest.from_file(ROOT / "dashboard/app.py").run(timeout=30)
    app.sidebar.radio[0].set_value("How the study works").run(timeout=30)
    prose = " ".join(element.value for element in [*app.markdown, *app.caption])
    assert "756 daily returns" in prose
    assert "monthly rebalancing" in prose
    assert "quarterly rebalancing" in prose
    assert "60% VT" in prose and "40% BND" in prose
    assert "gross amount traded" in prose
    assert app.metric[0].value == "10 bps = 0.10%"


def test_rebalancing_page_defines_bands_and_compares_policies() -> None:
    app = AppTest.from_file(ROOT / "dashboard/app.py").run(timeout=30)
    app.sidebar.radio[0].set_value("Rebalancing policies").run(timeout=30)
    prose = " ".join(element.value for element in [*app.markdown, *app.caption, *app.info])
    assert "±5 percentage-point band" in prose
    assert "20% target" in prose
    assert "15% to 25%" in prose
    assert len(app.dataframe) == 1
    assert len(app.get("plotly_chart")) == 1


def test_scenarios_and_empty_selection_are_explicit() -> None:
    app = AppTest.from_file(ROOT / "dashboard/app.py").run(timeout=30)
    app.sidebar.radio[0].set_value("Robustness").run(timeout=30)
    for family in ["Estimation windows", "Position limits", "Market regimes", "Costs"]:
        app.selectbox[0].set_value(family).run(timeout=30)
        assert not app.exception
    app.sidebar.radio[0].set_value("Out-of-sample results").run(timeout=30)
    app.multiselect[0].set_value([]).run(timeout=30)
    assert not app.exception
    assert len(app.info) == 1


@pytest.mark.skipif(
    not (ROOT / "locales/es.json").is_file(), reason="Local translation not published"
)
def test_spanish_has_the_same_sections_and_figures() -> None:
    app = AppTest.from_file(ROOT / "dashboard/app.py").run(timeout=30)
    app.sidebar.selectbox[0].set_value("es").run(timeout=30)
    assert app.title[0].value == "Visión general"
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run(timeout=30)
        assert not app.exception
    app.sidebar.radio[0].set_value("The benchmark").run(timeout=30)
    assert app.title[0].value == "El benchmark"
    assert len(app.metric) == 4
    app.sidebar.radio[0].set_value("How the study works").run(timeout=30)
    assert app.title[0].value == "Cómo funciona el estudio"
    assert app.metric[0].label == "Costo base"
