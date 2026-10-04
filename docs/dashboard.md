# Dashboard

The **Rebalancing policies** page explains the difference between target estimation and trade
execution. Readers can choose one allocation model and compare its monthly, quarterly and
three drift-band variants using the same performance and implementation measures. The page
defines a band in percentage points with a concrete 20% target example, so the threshold is
not confused with a relative price move.

Run `streamlit run dashboard/app.py` from the project root. The English edition is complete
on its own. A local `locales/es.json` enables the Spanish selector without duplicating pages.
Configuration is intentionally absent from navigation; assumptions appear beside the
results they explain. Editing assumptions belongs in `configs/`, followed by a study rebuild.

The reading order is overview → universe → benchmark → construction → results → risk →
comparison → robustness → conclusions. Downloads expose the same evidence as the charts.
The benchmark page explains instruments, drift, rebalancing, costs and the distinction
between the performance benchmark and the cash reference.

Charts use stable model colors and dotted monthly versus solid quarterly lines. Financial
tables format return and risk as percentages. Sensitivity views show dates and failed cases.
The dashboard reads current files on every rerun, avoiding stale in-memory report caches.
