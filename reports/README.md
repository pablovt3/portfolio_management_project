# Published Study Artifacts

This directory contains compact, derived research outputs intended for source
control, portfolio presentation, and the Streamlit dashboard. Raw and processed
Yahoo Finance data remain excluded from Git.

- `executive_summary.md` is the concise GitHub-readable report.
- `executive_summary.html` is the standalone interactive Plotly executive report.
- `figures/` contains selected static figures for README rendering.
- `data/` contains derived comparison and robustness tables, not raw prices.

Regenerate every file with:

```bash
python scripts/run_study.py
```
