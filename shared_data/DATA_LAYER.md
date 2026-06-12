# shared_data — read-only data layer

> **Access:** All agents read-only. No writes, deletes, or overwrites in this directory.

## Sample tier (current)

| File | Role | Scale (current checkout) |
|------|------|---------------------------|
| `sample_master_registration_data.xlsx` | Integrated registration / master | ~510 rows, 93 columns |
| `sample_transaction_supply_data.xlsx` | Supply details / transaction log | ~12.5k rows, 74 columns |

Column semantics and regulatory rules: `shared_docs/official/description_master_registration.md`, `description_transaction_supply.md`.

## Production tier (future)

PM may replace these files or designate new basenames using the same `sample_*` pattern or PM-directed paths. Agents must discover and profile inputs at runtime—never assume fixed row counts or column lists in code.

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
