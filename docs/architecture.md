# Architecture and code style

Read `research.run_study` first. It loads the cached prices once, runs the research stages
and publishes the evidence. Each stage accepts a price frame for deterministic testing.

- `config`: parse and validate the research contract before any calculation.
- `pipelines/data`: acquire, normalize and record source data.
- `pipelines/eda` and `construction`: call library diagnostics and optimizers.
- `pipelines/backtesting`: adapt the study's policies to library trading engines.
- `evaluation`: define the study's realized-cash convention using library primitives.
- `pipelines/robustness`: run explicit variations and keep unsuccessful outcomes visible.
- `pipelines/reporting`: publish a consistent evidence bundle.
- `presentation`: read that bundle and explain it in charts, tables and prose.

Prefer descriptive names and short functions. Comments explain a financial choice or timing
assumption, not what a Python statement obviously does. Keep pure calculations out of the
notebooks and dashboard. Do not add a generic framework where a small study adapter suffices.

English is the canonical publication language. Spanish markdown and a local translation
catalog provide equivalent narrative and charts. Both notebook editions use the same code
cells apart from the language code. No translation changes numerical calculations.
