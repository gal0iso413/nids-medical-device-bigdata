# Hermes skills (NIDS)

Version-controlled skills for [Hermes Agent](https://hermes-agent.nousresearch.com/) — mirrors `.cursor/rules/` governance without duplicating `shared_docs/`.

## One-time WSL setup

Add the repo skills directory to `~/.hermes/config.yaml`:

```yaml
skills:
  external_dirs:
    - /mnt/c/Users/wq240/Documents/Projects/NIDS/cursor/.hermes/skills
```

Restart or start a new `hermes chat` session. Verify with `skills_list` or `/nids-workspace`.

## Skill index

| Skill | Slash command | Use when |
|-------|---------------|----------|
| `nids-workspace` | `/nids-workspace` | Every NIDS session (isolation, PM protocol) |
| `nids-data-ingestion` | `/nids-data-ingestion` | Loading or profiling Excel sample tier |
| `nids-doc-routing` | `/nids-doc-routing` | Choosing which docs to read |
| `nids-class-1` | `/nids-class-1` | Class 1 anomaly detection agent |
| `nids-class-2` | `/nids-class-2` | Class 2 supply forecast agent |
| `nids-class-3` | `/nids-class-3` | Class 3 impact evaluation agent |
| `nids-phase-1-eda` | `/nids-phase-1-eda` | Phase 1 discovery task (all agents) |

## Typical Class 1 session

```bash
cd /mnt/c/Users/wq240/Documents/Projects/NIDS/cursor/class_1_anomaly_detection
hermes chat
```

First message (short):

```text
Apply nids-workspace, nids-class-1, nids-phase-1-eda.
Task: Phase 1 discovery — summary only until I say proceed.
```

Load **one** class skill per session. Do not combine `nids-class-2` or `nids-class-3` with Class 1.

## Cursor vs Hermes

| Cursor | Hermes |
|--------|--------|
| `.cursor/rules/multi-agent-orchestration.mdc` | `nids-workspace` |
| `class_*/.cursor/rules/agent-governance.mdc` | `nids-class-*` |
| Composer context | Skills + tool reads of `shared_docs/` |

Specs stay in `shared_docs/`; skills point to paths, they do not copy dictionary content.
