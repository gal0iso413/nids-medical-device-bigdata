# shared_docs — read-only documentation layer

Field dictionaries and onsite calibration for the current local-analysis
product. They do not define a runtime entrypoint. Ingestion, monthly facts,
and Class 1/3 execution follow `docs/data/`, `docs/decisions/`, and
`docs/specs/`.

## Tiers

| Tier | Path | Purpose |
|------|------|---------|
| **official** | `official/` | Program RFP context and master/supply field dictionaries |
| **structured** | `structured/onsite_visit1_summary.md` | Production data calibration (Visit 1, 2026-06-18) |

## Hierarchy of truth

1. `README.md` and `docs/data/local-analysis-turnkey-runbook.md`
2. `docs/decisions/` and `docs/specs/` — current product, model, and web contracts
3. `official/` — column semantics and regulatory definitions
4. `structured/onsite_visit1_summary.md` — production calibration evidence
