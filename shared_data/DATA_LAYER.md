# shared_data — read-only data layer

> **Access:** All agents read-only. No writes, deletes, or overwrites in this directory.

## Sample tier

| File | Role | Scale (current checkout) |
|------|------|---------------------------|
| `sample_master_registration_data.xlsx` | Integrated registration / master | ~510 rows, 93 columns |
| `sample_transaction_supply_data.xlsx` | Supply details / transaction log | ~12.5k rows, 74 columns |

Use for bootstrap EDA and pipeline smoke tests.

Column semantics and regulatory rules: `shared_docs/official/description_master_registration.md`, `description_transaction_supply.md`.

## Modeling tier (top7) — default for model work

Not final production data, but the **practical stand-in** for modeling until full national extracts arrive. Prefer `top7_*` over `sample_*` once sample-tier EDA passes.

| File | Role | Scale (profile at runtime) |
|------|------|----------------------------|
| `top7_master_registration_data.xlsx` | Registration / master (7 item licenses) | ~221 rows, 93 columns |
| `top7_transaction_supply_data.xlsx` | Supply report (see sheets below) | Multi-sheet — load supply sheet only |

### `top7_transaction_supply_data.xlsx` — sheet layout

| Sheet | Tab name | Role |
|-------|----------|------|
| 1 | `표지` (**개요** / overview) | Request metadata: period, license list, usage notes. **Not tabular supply data** — do not ingest for modeling. |
| 2 | `공급내역 실제자료` | Supply transaction rows. **This is the supply data sheet** (~704k rows, 71 columns). Use chunked reads. |

Agents must **discover sheets at runtime** (by tab name, not default first sheet). Column semantics match `description_transaction_supply.md`.

## Production tier (future)

Full-volume extracts (larger than top7). Same dictionaries and dynamic ingestion; swap basename or path per PM directive. Agents must discover and profile inputs at runtime—never assume fixed row counts, sheet names, or column lists in code.

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
