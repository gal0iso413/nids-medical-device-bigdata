# Class 1 Anomaly Detection

The active local/internal execution path uses the offline anchor runner and the
[turnkey local analysis runbook](../docs/data/local-analysis-turnkey-runbook.md).
Older multi-model and Streamlit material remains legacy/QA context, not the
default operational path.

This module runs the Class 1 supply-chain anomaly workflow with an anchor-month
rolling window.

## Anchor-based Pipeline

For anchor `YYYYMM`, all outputs are aligned to the same rolling window:

- Network (`network_edges`, `network_nodes`)
- BC / HHI / Price Z-score / timelag
- PyG graph export
- PyGOD model scores
- Step 4 evaluation
- Streamlit UI view

This avoids mixed-time comparisons (for example, rolling GNN vs all-history
baseline metrics).

## Output Layout

- Rolling baseline outputs:
  - `class_1_anomaly_detection/output/rolling/anchor_YYYYMM/`
- PyG artifacts:
  - `class_1_anomaly_detection/output/pyg/anchor_YYYYMM/`
- Model/evaluation outputs:
  - `class_1_anomaly_detection/output/ml/anchor_YYYYMM/`

Legacy top-level outputs under `class_1_anomaly_detection/output/` are still
kept for compatibility.

## Phase 1 Execution (single anchor)

Use one anchor first (recommended), then expand later.

```bash
python -m class_1_anomaly_detection.src.eda.run_graph_eda --anchor-month 202605
python -m class_1_anomaly_detection.src.experiments.export_pyg_graph --anchor-month 202605
python -m class_1_anomaly_detection.src.experiments.run_pygod_compare --anchor-month 202605 --models dominant gadnr
python -m class_1_anomaly_detection.src.experiments.run_step4_evaluation --anchor-month 202605
streamlit run class_1_anomaly_detection/app.py
```

## All-Anchors Batch

To run the full anchor pipeline across all available anchors, run in this order:

```bash
python -m class_1_anomaly_detection.src.eda.run_graph_eda --all-anchors
python -m class_1_anomaly_detection.src.experiments.export_pyg_graph --all-anchors
python -m class_1_anomaly_detection.src.experiments.run_pygod_compare --all-anchors --models dominant gadnr
python -m class_1_anomaly_detection.src.experiments.run_step4_evaluation --all-anchors
```

Batch summaries are written to:

- `class_1_anomaly_detection/output/pyg/export_all_anchors_summary.json`
- `class_1_anomaly_detection/output/ml/run_compare_all_anchors_summary.json`
- `class_1_anomaly_detection/output/ml/step4_evaluation_all_anchors_summary.json`

## Optional Baseline-Only Batch

To precompute rolling baseline metrics for all anchors:

```bash
python -m class_1_anomaly_detection.src.eda.run_graph_eda --all-anchors
```

## Prerequisites and Skip Behavior

- `export_pyg_graph --all-anchors` requires anchor rolling CSVs from `run_graph_eda`.
- `run_pygod_compare --all-anchors` requires per-anchor PyG artifacts.
- `run_step4_evaluation --all-anchors` requires per-anchor combined GNN score files.
- Anchors missing prerequisites are skipped and listed in each batch summary JSON.

## Reuse Behavior

`run_pygod_compare --reuse` uses strict fingerprint validation.
Reuse is allowed only when anchor/model/hyperparameter/input signatures match.
If not, the run retrains and writes fresh outputs.
