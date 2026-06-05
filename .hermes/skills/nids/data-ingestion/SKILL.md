---
name: nids-data-ingestion
description: NIDS sample data layer — Excel paths, runtime discovery, profiling, null guardrails, join keys. Use when loading shared_data workbooks or writing ingestion code.
version: 1.0.0
metadata:
  hermes:
    tags: [nids, data, excel, ingestion]
    category: nids
---

# NIDS Data Ingestion

## When to use

Loading sample workbooks, profiling schema, or implementing ingestion adapters inside an agent folder.

## Canonical source

Read at runtime: `shared_data/DATA_LAYER.md`

## Sample tier (current)

| File | Role |
|------|------|
| `shared_data/sample_master_registration_data.xlsx` | Integrated registration / master |
| `shared_data/sample_transaction_supply_data.xlsx` | Supply / transaction log |

Column semantics: `shared_docs/official/description_master_registration.md`, `description_transaction_supply.md`.

## Dynamic volatility (mandatory)

Ingestion code must:

1. **Discover** workbooks at runtime (configured basename or PM-declared path).
2. **Profile** each load: dtypes, null rates, cardinality, candidate keys.
3. **Scale** with volume (chunked reads when files exceed sample size).
4. **Tolerate drift** — new/removed columns trigger re-profile and PM notification, not silent failure.
5. **Keep adapters** inside the active agent folder; `shared_data/` stays read-only.

Never hardcode row counts or fixed column lists in production code.

## Guardrails

- Drop columns with **>50%** missing only during EDA/modeling per agent governance; flag **20–50%** as quality indicators.
- Join keys between master and supply follow official dictionaries (item / model / UDI-DI serial numbers).

## Procedure

1. Read `shared_data/DATA_LAYER.md`.
2. Load workbooks with `openpyxl` / pandas from the project venv.
3. Report observed row/column counts in summaries (discovery); do not bake counts into code.
4. On schema mismatch vs dictionaries, flag in summary and update agent `PROGRESS.md` if material.

## Verification

- No writes under `shared_data/` or `shared_docs/`.
- Profiling output matches files on disk at runtime.
