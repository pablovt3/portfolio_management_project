"""A guided research dashboard. Run with: streamlit run dashboard/app.py."""

import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

main = import_module("portfolio_management_project.presentation.dashboard").main

if __name__ == "__main__":
    main()
