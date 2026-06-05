---
name: nids-workspace
description: NIDS multi-agent workspace rules — directory isolation, read-only shared layers, PM control in Composer, English-only, Phase 1 default. Use at the start of every NIDS Hermes session.
version: 1.0.0
metadata:
  hermes:
    tags: [nids, workspace, governance]
    category: nids
---

# NIDS Workspace

## When to use

Start of **every** NIDS Hermes session before agent-specific work.

## Repository root

WSL path: `/mnt/c/Users/wq240/Documents/Projects/NIDS/cursor`

## Directory isolation

| Path | Access |
|------|--------|
| `shared_data/` | Read-only |
| `shared_docs/` | Read-only (PM-maintained) |
| `shared_utils/` | Immutable — import `AgentSlacker` only; do not edit |
| `class_1_anomaly_detection/` | Agent 1 writable root |
| `class_2_supply_forecast/` | Agent 2 writable root |
| `class_3_impact_evaluation/` | Agent 3 writable root |

Never modify files outside the active agent's writable root.

## Control protocol

- **PM commands:** Cursor Composer only (Hermes does not listen on Slack for commands).
- **Reporting:** Outbound Slack via `AgentSlacker` when implemented (`shared_utils/slacker.py`).
- **Language:** English only in code, comments, logs, UI, Slack, and agent-folder docs.

## Active phase (workspace default)

**Phase 1 — Autonomous EDA** is locked for all agents until PM explicitly approves advancement in Composer.

Do not implement Phase 2–4 pipelines without PM approval.

## Procedure

1. Confirm working directory (prefer the active agent folder).
2. Load the matching `nids-class-*` skill — never two class skills in one session.
3. Read that agent's `PROGRESS.md` before substantive work.
4. Use tools to read shared docs; do not paste full dictionaries into chat.

## Verification

- No writes outside the active `class_*` folder.
- Phase lock respected.
- Replies in English.
