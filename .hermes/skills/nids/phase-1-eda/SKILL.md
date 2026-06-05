---
name: nids-phase-1-eda
description: NIDS Phase 1 autonomous EDA — profile sample Excel, align columns to official dictionaries, summarize ingestion rules, update PROGRESS.md, HALT before scripts unless PM says proceed. Use for all agents in Phase 1.
version: 1.0.0
metadata:
  hermes:
    tags: [nids, phase-1, eda]
    category: nids
---

# Phase 1 — Autonomous EDA

## When to use

Active agent is in **Phase 1 (locked)** and PM has not yet approved Phase 2+.

Combine with `nids-workspace`, one `nids-class-*`, and optionally `nids-data-ingestion` / `nids-doc-routing`.

## Deliverable modes

| PM instruction | Output |
|----------------|--------|
| Discovery (default) | Written summary only — **no EDA scripts** until PM says "proceed with scripts" |
| After approval | Scripts under active agent writable root only |

## Procedure (discovery)

1. Follow doc hierarchy from active `nids-class-*` skill.
2. Load sample workbooks from `shared_data/`; report sheet names, row/column counts, dtypes, null rates for key columns.
3. Compare observed column names to official dictionaries (Korean/English labels, UDI-DI, supplier fields, join keys).
4. Summarize ingestion rules from `DATA_LAYER.md`; flag mismatches (missing columns, unexpected names, join-key issues).
5. Update agent `PROGRESS.md` with one bullet if doc sync or phase state changed (≤20 lines total).

## Python environment

If a project venv exists at repo root `.venv`, activate before running Python:

```bash
source /mnt/c/Users/wq240/Documents/Projects/NIDS/cursor/.venv/bin/activate
```

If venv is missing, report and stop — do not `pip install` without PM approval.

Use `openpyxl` for Excel reads. Do not upgrade pinned packages without PM approval.

## Stop conditions

- Phase 1 discovery complete → deliver summary → **HALT**
- Do not auto-advance to strategy, MVP, or refactor phases
- Do not write implementation pipelines until PM approves

## Verification

- Summary covers both workbooks (when agent uses both) and dictionary alignment.
- No files written outside active `class_*` folder (except `PROGRESS.md` update).
- No full EDA scripts unless PM explicitly requested.
