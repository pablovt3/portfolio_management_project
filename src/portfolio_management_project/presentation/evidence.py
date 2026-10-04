"""Read one published study and reject mismatched assumptions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from portfolio_management_project.config import load_research_config


class Evidence:
    """Serve the same saved evidence to the notebook and dashboard."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.config = load_research_config(root / "configs")
        self.directory = root / "reports" / "data"
        self.manifest = json.loads((self.directory / "study_manifest.json").read_text())
        if self.manifest.get("schema_version") != 2:
            raise ValueError("Rebuild the study to use the current reporting conventions.")
        if self.manifest["config_digest"] != self.config.config_digest:
            raise ValueError("The assumptions changed after publication. Rebuild the study.")

    def table(self, name: str, levels: int = 1) -> pd.DataFrame:
        """Load a declared table. Multi-level indices retain their original meaning."""
        if name not in self.manifest["public_tables"]:
            raise KeyError(f"Unknown evidence table: {name}")
        index: int | list[int] = 0 if levels == 1 else list(range(levels))
        path = self.directory / f"{name}.csv"
        expected = self.manifest.get("table_sha256", {}).get(name)
        if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Evidence changed after publication: {name}")
        return pd.read_csv(path, index_col=index)

    def dates(self, name: str) -> pd.DataFrame:
        """Read a time series with dates rather than strings on the horizontal axis."""
        frame = self.table(name)
        frame.index = pd.to_datetime(frame.index)
        return frame
