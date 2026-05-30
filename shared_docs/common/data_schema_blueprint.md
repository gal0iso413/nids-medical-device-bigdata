# Data Schema Blueprint (Common Context)

> **Status:** Placeholder — PM to align with production schemas and business definitions.

## Relationship to `shared_data/`

- Executable sample/prod files live under `shared_data/` (`sample_*` prefix today).
- This document defines **how** agents ingest and profile data, not fixed column inventories.

## Dynamic ingestion principles

1. **Discover** inputs at runtime; do not hardcode row counts or column lists.
2. **Profile** each load: dtypes, null rates, cardinality, candidate keys.
3. **Scale** for production volume (chunking, bounded aggregates).
4. **Adapt** to structural drift; notify PM via `AgentSlacker` when schema shifts invalidate prior assumptions.
5. **Guardrails:** Drop >50% missing columns (document drops); flag 20–50% missing as quality indicators.

## Canonical sample paths (current tier)

| File | Role |
|------|------|
| `shared_data/sample_master_registration_data.xlsx` | Registry / master |
| `shared_data/sample_transaction_supply_data.xlsx` | Transaction / supply log |

## PM extensions (TBD)

- Production basename mapping
- Primary / foreign key declarations
- PII and redaction columns
- Unit and timezone standards

See also `shared_data/DATA_LAYER.md` for operational data-layer rules.
