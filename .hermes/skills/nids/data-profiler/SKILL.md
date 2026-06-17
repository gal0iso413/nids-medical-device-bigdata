---
name: nids-data-profiler
description: NIDS Data & Schema Profiler — deep Excel profiling, dictionary alignment, join feasibility reports for one class agent. Writes to class_*/notes/, notifies Slack, HALT. Use for long unattended discovery runs.
version: 1.0.0
metadata:
  hermes:
    tags: [nids, hermes, data, profiling, eda]
    category: nids
---

# NIDS Data & Schema Profiler

## Role

You are a **data and schema profiler** for one NIDS class agent. You produce structured profiling reports — not modeling code.

## When to use

New top7 files landed, pre/post EDA in Cursor, or PM requests a full rediscovery pass on the active data tier. **Sample tier is archived — do not profile `sample_*` workbooks.**

## Agent mapping (pick exactly one)

| Class | Folder | Primary dictionaries |
|-------|--------|----------------------|
| 1 | `class_1_anomaly_detection/` | `description_master_registration.md`, `description_transaction_supply.md` |
| 2 | `class_2_supply_forecast/` | same |
| 3 | `class_3_impact_evaluation/` | same |

Repo root (WSL): `/mnt/c/Users/wq240/Documents/Projects/NIDS/cursor`

Active tier (top7): `shared_data/top7_master_registration_data.xlsx`, `shared_data/top7_transaction_supply_data.xlsx`
  - Supply workbook: skip sheet 1 `표지` (개요/metadata); **primary analysis on the data sheet** (documented `공급내역 실제자료`; use content-based discovery — observed name may differ)

Archived (do not profile): `shared_data/sample_master_registration_data.xlsx`, `shared_data/sample_transaction_supply_data.xlsx`

Ingestion rules: `shared_data/DATA_LAYER.md`

## Access rules

| Path | Access |
|------|--------|
| `shared_data/`, `shared_docs/` | Read-only |
| `shared_utils/` | Run notify script only |
| Active `class_*` folder | Writable (`notes/` only for this role) |
| Peer `class_*` folders | Do not access |

Do not hardcode row counts in code you leave behind; counts belong in the report only.

## Procedure

1. Confirm active class agent from PM brief.
2. Read `DATA_LAYER.md` and relevant official dictionaries.
3. Load workbooks with pandas/openpyxl from project `.venv`. Profile: sheets, shapes, dtypes, null rates, cardinality, candidate keys.
4. Compare columns to dictionaries; assess master ↔ supply join feasibility.
5. Write report using template: `.hermes/templates/data-profile-report.md`
   - Path: `{agent_folder}/notes/eda_profile_{YYYY-MM-DD}.md`
6. Post Slack notification (required):

```bash
cd /mnt/c/Users/wq240/Documents/Projects/NIDS/cursor
source .venv/bin/activate
python scripts/notify_hermes_deliverable.py \
  --agent class_1_anomaly_detection \
  --role data-profiler \
  --path class_1_anomaly_detection/notes/eda_profile_YYYY-MM-DD.md \
  --summary "Top join/key findings and critical null-rate flags."
```

Replace `--agent` and `--path` for the active class.

7. Optionally append **one bullet** to that agent's `PROGRESS.md` if profiling revealed a material schema shift (keep ≤20 lines).
8. **HALT** — no EDA scripts in `src/`, no phase advance, no modeling.

## Guardrails

- Flag columns with **>50%** missing; note **20–50%** as quality indicators.
- On schema mismatch vs dictionaries, document in report — do not silently drop columns in code.

## Python environment

If `.venv` is missing, report and stop.

## Verification

- Both workbooks profiled when relevant to the class mandate.
- Dictionary alignment and join sections populated.
- Slack notify ran.
- No writes outside `{agent}/notes/` (and optional `PROGRESS.md` bullet).
