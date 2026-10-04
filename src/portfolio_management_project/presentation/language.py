"""English is the published language; optional local catalogs add translations."""

from __future__ import annotations

import json
import re
from pathlib import Path


class Language:
    """Translate presentation text without duplicating calculations or page logic."""

    def __init__(self, root: Path, code: str = "en") -> None:
        self.code = code
        self.catalog: dict[str, str] = {}
        if code != "en":
            self.catalog = json.loads((root / "locales" / f"{code}.json").read_text())

    def __call__(self, text: str) -> str:
        return self.catalog.get(text, text)

    def strategy(self, name: str) -> str:
        if name == "benchmark_60_40":
            return self("Global 60/40")
        models = {
            "equal_weight": "Equal weight",
            "minimum_variance": "Minimum variance",
            "mean_variance": "Mean–variance",
            "target_return": "Target return",
            "maximum_sharpe": "Maximum Sharpe",
        }
        for model, label in models.items():
            if name == model:
                return self(label)
            for frequency in ("monthly", "quarterly"):
                if name == f"{model}_{frequency}":
                    return f"{self(label)} · {self(frequency)}"
            match = re.fullmatch(rf"{model}_band_(\d+)bp", name)
            if match:
                points = int(match.group(1)) / 100
                return f"{self(label)} · {self('drift band')} ±{points:g} pp"
        return self(name.replace("_", " ").capitalize())

    def column(self, name: str) -> str:
        special = {
            "annualized_return": "Annualized return (CAGR)",
            "annualized_volatility": "Annualized volatility",
            "sharpe_ratio": "Sharpe vs cash",
            "maximum_drawdown": "Maximum drawdown",
            "balanced_rank_score": "Average rank",
            "overall_rank": "Overall rank",
            "final_value": "Final wealth",
            "information_ratio": "Information ratio",
            "total_turnover": "Total turnover",
            "average_max_weight": "Average largest position",
            "calmar_ratio": "Calmar ratio",
        }
        return self(special.get(name, name.replace("_", " ").capitalize()))
