# shared_utils (immutable for agents)

## `slacker.py`

Mandatory outbound Slack bridge. Agents must not fork or edit this module.

| Variable | Scope | Routes to |
|----------|--------|-----------|
| `SLACK_WEBHOOK_URL` | Per-agent `.env` | Agent project channel |
| `SLACK_GENERAL_WEBHOOK_URL` | Root `.env` | `#general-pm-board` |

### API surface

- `notify_phase_completion(..., broadcast_global=False)` — agent channel; optional global mirror
- `notify_hermes_deliverable(role, deliverable_path, summary, ...)` — Hermes role report saved on disk
- `escalate_roadblock(..., broadcast_global=False)` — agent channel; optional global mirror
- `broadcast_global_sync(subject, message)` — global channel only (cross-agent sync)

Hermes roles invoke `scripts/notify_hermes_deliverable.py` after writing a report. Roles: `methods-researcher`, `data-profiler`, `spec-auditor`.

### Control loop (PM decision)

**Outbound only.** Agents report to Slack; the PM never drives code execution via Slack. All phase advances, parameter changes, and unblocks happen in **Cursor Composer**.
