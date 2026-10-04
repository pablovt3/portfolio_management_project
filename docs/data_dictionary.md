# Data Dictionary

## Configuration

| File | Purpose |
|---|---|
| `configs/base.yaml` | Project currency, study dates, provider settings, and output paths |
| `configs/universe.yaml` | Governed investable assets, economic sleeves, roles, and exclusions |
| `configs/benchmark.yaml` | External benchmark constituents, target weights, and cash hurdle |

## Generated datasets

| Artifact | Contents |
|---|---|
| `data/raw/yahoo_market_data_<hash>.csv` | Canonical OHLCV fields returned through `MarketData.data` |
| `data/raw/yahoo_adjusted_close_<hash>.csv` | Selected adjusted-close matrix in governed ticker order |
| `data/processed/adjusted_close.csv` | Current analysis-ready adjusted-close matrix |
| `data/processed/data_quality.csv` | Per-ticker coverage, missingness, and nonpositive-price counts |
| `data/manifests/market_data_<hash>.json` | Versions, configuration/data hashes, dates, tickers, validation, and lineage |
| `artifacts/eda/tables/*.csv` | Reusable EDA tables returned by library analytics |
| `artifacts/eda/figures/*.html` | Interactive figures produced by library visualization components |
| `artifacts/eda/eda_summary.md` | Concise sample-dependent financial interpretation |

The raw hash is the SHA-256 digest of a deterministic CSV serialization of the
canonical market-data frame. Existing content-addressed raw files are never
overwritten with different bytes.

## Date conventions

- Dates are stored as ISO `YYYY-MM-DD` values.
- Yahoo Finance's configured end date is exclusive.
- The data frequency is daily (`1d`).
- The selected price field is `Adj Close` with `auto_adjust=False`.
