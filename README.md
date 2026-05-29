# NIDS Multi-Agent Orchestration Workspace

Three isolated agents share read-only Excel inputs and the immutable Slack bridge in `shared_utils/slacker.py`.

## Layout

| Path | Role |
|------|------|
| `shared_data/` | Read-only datasets (`sample_*` prefix today) |
| `shared_utils/` | Immutable `AgentSlacker` (agent + `#general-pm-board`) |
| `class_1_anomaly_detection/` | Agent 1 — distribution & graph anomalies |
| `class_2_supply_forecast/` | Agent 2 — time-series & early warning |
| `class_3_impact_evaluation/` | Agent 3 — MCDM & portfolio reporting |
| `.cursor/rules/` | Workspace governance (MDC) |

Per-agent governance lives in `class_*/.cursor/rules/agent-governance.mdc`.

## Data files

- `shared_data/sample_master_registration_data.xlsx`
- `shared_data/sample_transaction_supply_data.xlsx`

See `shared_data/DATA_LAYER.md` for dynamic ingestion and production swap rules.

## Environment

| File | Variables |
|------|-----------|
| Root `.env` | `SLACK_GENERAL_WEBHOOK_URL` → `#general-pm-board` |
| `class_*/.env` | `SLACK_WEBHOOK_URL` → agent project channel |

Copy from `.env.example` files. Webhooks are optional for local work.

## Control protocol

- Agents **report** via Slack (`AgentSlacker`).
- PM **commands** only in Cursor Composer (no Slack-to-code listener).

## Phase status

All agents are locked at **Phase 1 (EDA)** until the PM approves advancement in Composer.

## Sample data

```powershell
python scripts/generate_sample_data.py
```

Implementation code (Streamlit pipelines, models) is added only after phase approvals.
