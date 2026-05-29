# shared_data — read-only data layer

## Canonical filenames (current sample tier)

| File | Role |
|------|------|
| `sample_master_registration_data.xlsx` | Registry / master entities |
| `sample_transaction_supply_data.xlsx` | Time-series transaction / supply log |

Production files may replace these paths later using the same basename pattern or PM-directed renames. Agents must resolve inputs dynamically (see agent `.cursor/rules` ingestion protocol).

## Dynamic volatility adaptation (mandatory)

Ingestion pipelines must:

1. **Discover** workbooks at runtime (configured basename or PM-declared path); never assume fixed row counts or column lists in code.
2. **Profile** schema on each load: dtypes, null rates, cardinality, and candidate keys.
3. **Scale** with volume: prefer chunked reads, bounded aggregates, and caching only after schema validation when production files exceed sample size.
4. **Tolerate structural drift**: new or removed columns trigger EDA re-profile and PM notification—not silent failure or hardcoded column access without guards.
5. **Preserve architecture**: adapters live inside each agent folder; `shared_data/` stays read-only.

## Guardrails

- No agent writes, deletes, or overwrites files in this directory.
- Drop columns with **>50%** missing only during EDA/modeling phases per governance rules; flag **20–50%** as quality indicators.
