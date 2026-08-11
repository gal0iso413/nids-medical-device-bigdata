# shared_docs — read-only documentation layer

Segregates domain knowledge from transactional data (`shared_data/`). Agents may read; only the PM updates content unless explicitly delegated.

## Tiers

| Tier | Path | Purpose |
|------|------|---------|
| **official** | `official/` | Stakeholder specifications: program RFP, master/supply field dictionaries |
| **structured** | `structured/` | Per-agent analytical mandates (제안서 / 착수보고서 bodies); onsite production calibration |

Data ingestion and file paths live in `shared_data/DATA_LAYER.md` (not in this tree).

## Hierarchy of truth

1. `shared_data/DATA_LAYER.md` — canonical source paths, ingestion guardrails
2. `official/` — column semantics and regulatory definitions
3. `structured/onsite_visit1_summary.md` — production data calibration (Visit 1, 2026-06-18)
4. `../docs/decisions/` and `../docs/specs/` — current product, model, web, and migration contracts
5. `structured/class_X_*_spec.md` — historical analytical mandates retained as source context; where they conflict with the current decision documents, the current decision documents govern implementation

Agents load context per `class_*/.cursor/rules/agent-governance.mdc`. Do not cross-read peer structured specs.
