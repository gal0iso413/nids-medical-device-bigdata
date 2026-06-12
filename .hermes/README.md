# Hermes roles (NIDS)

Three **background specialist roles** for [Hermes Agent](https://hermes-agent.nousresearch.com/). Governance and implementation stay in **Cursor** (`.cursor/rules/`). Hermes handles bounded, long, or unattended work and posts deliverables to Slack.

## One-time WSL setup

Add the repo skills directory to `~/.hermes/config.yaml`:

```yaml
skills:
  external_dirs:
    - /mnt/c/Users/wq240/Documents/Projects/NIDS/cursor/.hermes/skills
```

Restart or start a new `hermes chat` session. Verify with `skills_list` or `/nids-methods-researcher`.

## Role index

| Skill | Slash command | Output folder | Purpose |
|-------|---------------|---------------|---------|
| `nids-methods-researcher` | `/nids-methods-researcher` | `class_*/research/` | Literature & methods briefs |
| `nids-data-profiler` | `/nids-data-profiler` | `class_*/notes/` | Excel profiling & dictionary alignment |
| `nids-spec-auditor` | `/nids-spec-auditor` | `class_*/notes/` | Read-only spec vs data vs code audit |

Report templates: `.hermes/templates/`

## Typical session

```bash
cd /mnt/c/Users/wq240/Documents/Projects/NIDS/cursor/class_1_anomaly_detection
hermes chat
```

First message (one role, one class, one deliverable):

```text
Apply nids-methods-researcher.
Class: class_1_anomaly_detection.
Task: Compare PDI + betweenness + HHI vs graph outlier methods for indirect supply detection.
Constraints: ~12.5k supply rows, interpretable for regulators.
Write: class_1_anomaly_detection/research/2025-06-network-methods.md
Then notify Slack and HALT.
```

## Slack notification (required)

Each role finishes by running from repo root:

```bash
source .venv/bin/activate
python scripts/notify_hermes_deliverable.py \
  --agent class_1_anomaly_detection \
  --role methods-researcher \
  --path class_1_anomaly_detection/research/2025-06-network-methods.md \
  --summary "Short summary for the channel."
```

Webhooks: `SLACK_WEBHOOK_URL` in `class_*/.env`; optional `SLACK_GENERAL_WEBHOOK_URL` in root `.env`.

## Cursor vs Hermes

| Cursor | Hermes |
|--------|--------|
| PM commands, phase gates, code + diffs | Background research, profiling, audits |
| `.cursor/rules/` governance | Three role skills only |
| Interactive review | Deliverable markdown + Slack record |

Do **not** load multiple Hermes roles in one session. Do **not** recreate per-phase governance skills.
