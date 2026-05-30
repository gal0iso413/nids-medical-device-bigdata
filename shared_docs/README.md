# shared_docs — read-only documentation layer

Segregates domain knowledge from transactional data (`shared_data/`). Agents may read; only the PM updates content unless explicitly delegated.

## Tiers

| Tier | Path | Purpose |
|------|------|---------|
| **official** | `official/` | Immutable stakeholder governance logs (raw) |
| **structured** | `structured/` | PM-modularized agent specifications |
| **common** | `common/` | Universal context for all agents |

## Hierarchy of truth

1. `common/` — universal baseline
2. `structured/class_X_*_spec.md` — overrides `common/` for that agent when in conflict
3. `official/` — stakeholder source material; does not override structured specs without PM reconciliation

Agents load context per `.cursor/rules` anchoring protocol.
