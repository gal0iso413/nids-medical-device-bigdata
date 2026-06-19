# shared_docs — read-only documentation layer

Segregates domain knowledge from transactional data (`shared_data/`). Agents may read; only the PM updates content unless explicitly delegated.

## Tiers

| Tier | Path | Purpose |
|------|------|---------|
| **official** | `official/` | Stakeholder specifications: program RFP, master/supply field dictionaries |
| **structured** | `structured/` | Per-agent analytical mandates (제안서 / 착수보고서 bodies); onsite production calibration |

Data ingestion and file paths live in `shared_data/DATA_LAYER.md` (not in this tree).

## Hierarchy of truth

1. `shared_data/DATA_LAYER.md` — canonical paths, dynamic ingestion, guardrails
2. `official/` — column semantics and regulatory definitions
3. `structured/onsite_visit1_summary.md` — production data calibration (Visit 1, 2026-06-18)
4. `structured/class_X_*_spec.md` — **supreme** for that agent’s scope when in conflict with official interpretations

Agents load context per `class_*/.cursor/rules/agent-governance.mdc`. Do not cross-read peer structured specs.
