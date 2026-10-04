# Contributing

## Development setup

Install the core library and this study in editable mode:

```bash
conda activate pm_project
python -m pip install -e '../portfolio_management_module[dev]'
python -m pip install -e '.[dev,dashboard,report]'
```

## Architecture

Reusable financial calculations belong in `portfolio-management-module`.
This repository owns only the governed experiment, orchestration, reporting,
dashboard, and study-specific interpretation. Notebooks and the dashboard must
remain thin clients of tested APIs and exported research tables.

## Quality gates

```bash
make quality
```

Changes should include type hints, docstrings, tests, and documentation. Raw
market data, caches, credentials, and generated artifacts must not be committed.
