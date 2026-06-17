# shared_data — read-only data layer

> **Access:** All agents read-only. No writes, deletes, or overwrites in this directory.

## Active tier (top7) — default for all agents

| File | Role | Scale |
|------|------|-------|
| `top7_master_registration_data.xlsx` | Integrated registration / master | ~221 rows, 93 columns |
| `top7_transaction_supply_data.xlsx` | Supply details / transaction log | ~704k rows, 71 columns |

Supply workbook: **two sheets** — sheet 1 `표지` (개요/metadata, skip); **sheet 2 is the data sheet** (documented as `공급내역 실제자료`; observed name `공급내역 보고자료`). Use **content-based sheet discovery** — do not hardcode the sheet name.

Column semantics and regulatory rules: `shared_docs/official/description_master_registration.md`, `description_transaction_supply.md`.

## Archived tier (sample) — do not load

Legacy files retained in the repo solely as audit trail for early Hermes bootstrap runs. Agents **must not** ingest, profile, join, or reference these workbooks in any code path.

| File | Note |
|------|------|
| `sample_master_registration_data.xlsx` | Superseded by top7; 0% master/supply join overlap |
| `sample_transaction_supply_data.xlsx` | Superseded by top7; disjoint product population |

## Dynamic volatility adaptation (mandatory)

Ingestion pipelines must:

1. **Discover** workbooks at runtime (configured basename or PM-declared path).
2. **Profile** schema on each load: dtypes, null rates, cardinality, and candidate keys.
3. **Scale** with volume: chunked reads, bounded aggregates, caching only after schema validation when files exceed sample size.
4. **Tolerate structural drift**: new or removed columns trigger EDA re-profile and PM notification via `AgentSlacker`—not silent failure or unguarded column access.
5. **Preserve architecture**: adapters live inside each agent folder; `shared_data/` stays read-only.

## Guardrails

- Drop columns with **>50%** missing only during EDA/modeling per agent governance; flag **20–50%** as quality indicators.
- Join keys between master and supply follow official dictionaries (item / model / UDI-DI serial numbers).

## Related documentation

| Topic | Path |
|-------|------|
| Agent mandate | `shared_docs/structured/class_*_*_spec.md` |
| Program / RFP context | `shared_docs/official/medical_device_bigdata_spec.md` (PM-directed) |
| Workspace rules | `.cursor/rules/multi-agent-orchestration.mdc` |
