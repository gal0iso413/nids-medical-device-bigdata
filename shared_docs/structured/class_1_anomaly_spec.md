# Class 1 — Anomaly Detection Specification

> **Status:** Active — final model concept locked (meeting + innovation prototype handoff).
> **Authority:** Supersedes `official/` interpretations for Agent 1 analytical mandate when in conflict.

## Scope

- Internal NIDS policy-monitoring reference for anomalous distribution structures
- Firm-entity directed supply graph + unsupervised GNN scoring (GAD-NR production default)
- Rule metrics (BC, PDI, HHI, robust price z, timelag) as **auxiliary evidence only**
- Class 2 is out of scope for this deliverable

## Purpose framing (mandatory)

- Outputs are **internal reference** for supply-chain policy monitoring (e.g. shortage / irregular routing watch).
- Not a sanction, enforcement, or public company-scoring product.
- UI and exports must carry an internal-use disclaimer.
- BC hub ranking and GNN review ranking must never be presented as the same list.

## Production ranking contract

| Role | Signal | UI use |
|------|--------|--------|
| **Primary review rank** | GAD-NR anomaly score (firm nodes) | “확인 필요 업체” list sort key |
| **Discovery / hub view** | Betweenness centrality (BC) | Optional top-N overview only; labeled ≠ AI review |
| **Auxiliary evidence chips** | PDI, HHI, price z, timelag (+ BC as chip) | Facts / interpretation templates; never primary sort |

Production model slug: `gadnr`. Other PyGOD models may be compared offline; switching the production default requires an explicit PM note in this file.

## Graph strategy

- **Implemented:** firm-entity directed graph over a **3-month rolling anchor window**.
- Edges pre-aggregated for density control: prefer `(supplier, receiver[, item_group])` weights for GNN skeleton; product-level detail retained where needed for PDI/path evidence.
- **Not implemented (documented only):** UDI-centric GNN — see `class_1_anomaly_detection/notes/udi_centric_gnn_future.md`.

## Train / display split (GNN)

- **Train anchors:** earliest usable months up to a cutoff recorded in the run manifest (`train_anchor_months`).
- **Display anchors:** all (or latest N) anchors scored with the frozen GAD-NR weights; retrain on schedule only.
- Metrics/UI always use the selected display anchor’s rolling window artifacts.

## Data path

1. Materialize Excel (top7 active tier) → agent-local **Parquet** partitions (`class_1_anomaly_detection/data/parquet/`).
2. Offline batch: rolling graph + rules → PyG export (slim production features) → GAD-NR train/infer → **UI artifact bundle**.
3. Streamlit reads **precomputed artifacts only** (no live Excel, no full-graph render).

Scale path: chunked Parquet; ego/subgraph caps; optional degree prune if OOM; GPU offline training preferred.

## UI journey (Streamlit, Korean)

1. Internal-reference banner  
2. Company search + anchor select  
3. Hero brief (counts / change)  
4. Spotlight ego (1-hop default, optional 2-hop); edge width = report count \| quantity; node size = degree  
5. Optional BC top-N overview (discovery)  
6. Review deck ranked by GAD-NR + auxiliary chips + three-part explanation (관찰된 사실 / 모형의 해석 / 확인할 질문)  
7. Soft watchlist / saved searches (no alerts)  
8. Manual event-calendar flags when window overlaps known shocks  

## Artifact layout (per anchor)

`class_1_anomaly_detection/output/ui/anchor_YYYYMM/`

- `review_list.csv` — GAD-NR rank + auxiliary columns  
- `entity_evidence.json` — explanation template payloads  
- `ego/{entity_id}.json` — capped 1–2 hop subgraph  
- `top_n_overview.json` — BC discovery map  
- `events.json` — shock calendar overlay for the window  
- Watchlist: user-local JSON (not shared)

Rolling baselines remain under `output/rolling/anchor_YYYYMM/`; ML under `output/ml/anchor_YYYYMM/`.

## Batch handoff (next-year prep)

Column schemas under `class_1_anomaly_detection/exports/` (CSV/Parquet headers). No live UDI-portal API in this contract.

## Historical bodies (제안서 / 착수보고서)

Retained for audit. Where they conflict with the production ranking contract above (e.g. composite rule score as primary, GraphSAGE/Node2Vec as production, public scoring), **this file’s production sections win**.

### Initial Document (제안서) — archive summary

Network construction from supply reports; PDI / BC / HHI / price z heuristics; earlier composite `AnomalyScore` from rule indicators.

### Main Document (착수보고서) — archive summary

Entity/device/edge field lists; MAD price z; graph ML exploration; 0–100 score and network visualizer concepts.

---
