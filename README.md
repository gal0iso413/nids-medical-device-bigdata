# NIDS Multi-Agent Orchestration Workspace

Three isolated agents share read-only Excel inputs and the immutable Slack bridge in `shared_utils/slacker.py`.

## Layout

| Path | Role |
|------|------|
| `shared_data/` | Read-only datasets (`sample_*`, `top7_*`); see `DATA_LAYER.md` |
| `shared_docs/` | Read-only docs (`official/`, `structured/`) |
| `shared_utils/` | Immutable `AgentSlacker` (agent + `#general-pm-board`) |
| `class_1_anomaly_detection/` | Agent 1 — distribution & graph anomalies |
| `class_2_supply_forecast/` | Agent 2 — time-series & early warning |
| `class_3_impact_evaluation/` | Agent 3 — MCDM & portfolio reporting |
| `.cursor/rules/` | Workspace governance (MDC) |
| `.hermes/skills/` | Hermes background roles (research, profiler, auditor; see `.hermes/README.md`) |

Per-agent governance lives in `class_*/.cursor/rules/agent-governance.mdc`. Each agent maintains a compact `PROGRESS.md` (≤20 lines).

## Hermes Agent (background roles)

Three specialist roles for long or unattended work: methods research, data profiling, spec audit. Each writes a markdown deliverable and notifies Slack. Implementation and phase gates remain in **Cursor Composer**. Register skills once in WSL `~/.hermes/config.yaml` — see [.hermes/README.md](.hermes/README.md).

## Documentation (`shared_docs/`)

See `shared_docs/README.md`. Agents anchor: `shared_data/DATA_LAYER.md` → `official/` field dictionaries → their `structured/class_X_*_spec.md` (overrides on conflict). Do not cross-read peer specs.

## Data files

**Active tier (top7)** — sole data source for all agents:

- `shared_data/top7_master_registration_data.xlsx` (~221 × 93)
- `shared_data/top7_transaction_supply_data.xlsx` — sheet 1 `표지` (개요/metadata, skip); **data sheet** (~704k × 71) — discover by content, do not hardcode sheet name

**Archived tier (sample)** — do not use in code:

- `shared_data/sample_master_registration_data.xlsx` — retained for Hermes audit history only
- `shared_data/sample_transaction_supply_data.xlsx` — retained for Hermes audit history only; 0% master/supply join overlap

See `shared_data/DATA_LAYER.md` for ingestion rules.

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

Implementation code (Streamlit pipelines, models) is added only after phase approvals.
