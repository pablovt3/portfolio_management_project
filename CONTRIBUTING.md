# Contributing

The research currently depends on a private development version of
`portfolio-management-module`. Repository CI receives read-only access through a dedicated
deploy key pinned to a reviewed module commit. For security, GitHub does not expose that key
to workflows opened from forks, so the quality job runs for `main` and same-repository pull
requests while the module remains private.

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
