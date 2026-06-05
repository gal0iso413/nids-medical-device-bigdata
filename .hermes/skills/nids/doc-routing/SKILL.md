---
name: nids-doc-routing
description: NIDS documentation hierarchy — which files to read, in what order, and which peer specs to avoid. Use before reading shared_docs or interpreting column semantics.
version: 1.0.0
metadata:
  hermes:
    tags: [nids, docs, hierarchy]
    category: nids
---

# NIDS Documentation Routing

## When to use

Before reading domain specs or resolving conflicts between documents.

## Tiers

| Tier | Path | Purpose |
|------|------|---------|
| Data layer | `shared_data/DATA_LAYER.md` | Paths, ingestion, guardrails |
| Official | `shared_docs/official/` | RFP, field dictionaries (stakeholder source) |
| Structured | `shared_docs/structured/class_X_*_spec.md` | Per-agent mandate — **supreme for that agent on conflict** |

Overview: `shared_docs/README.md`

## Hierarchy of truth

1. `shared_data/DATA_LAYER.md`
2. Relevant `shared_docs/official/` dictionaries (see active `nids-class-*` skill)
3. That agent's `shared_docs/structured/class_X_*_spec.md`

## Cross-read rules

- **Do not** read peer structured specs (e.g. Class 1 must not open `class_2_forecast_spec.md` or `class_3_evaluation_spec.md`).
- Read `shared_docs/official/medical_device_bigdata_spec.md` only when PM directs.

## Procedure

1. Load active `nids-class-*` skill for agent-specific anchor list.
2. Read files in hierarchy order using file tools — do not copy full dictionaries into chat.
3. On conflict: structured spec for **this agent** wins over informal interpretation of official docs.

## Verification

- Only docs allowed for the active agent were read.
- No modifications under `shared_docs/`.
