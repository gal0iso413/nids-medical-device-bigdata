# Class 1 Anomaly Detection

Internal supply-chain review workflow. Production ranking: **GAD-NR**.
Rule metrics (BC, PDI, HHI, price z, timelag) are auxiliary evidence only.

## Pipeline (offline)

```bash
# 1) Excel → Parquet (once; UI/train never reopen Excel)
python -m class_1_anomaly_detection.src.ingest.materialize_parquet

# 2) Rolling firm graph + rule metrics (+ firm-aggregated edges)
python -m class_1_anomaly_detection.src.eda.run_graph_eda --anchor-month 202605

# 3) Slim PyG export (firm edges by default)
python -m class_1_anomaly_detection.src.experiments.export_pyg_graph --anchor-month 202605

# 4) GAD-NR production train/display (optional --compare-others)
python -m class_1_anomaly_detection.src.experiments.run_gadnr_production --anchor-month 202605

# 5) UI artifact bundle (ego caps, review list, events)
python -m class_1_anomaly_detection.src.experiments.build_ui_artifacts --anchor-month 202605

# 6) Streamlit (artifacts only)
streamlit run class_1_anomaly_detection/app.py
```

Batch all anchors with `--all-anchors` where supported.

## ML dependencies (required for `pyg_data.pt` + GAD-NR)

Install into the **same** conda env you run the pipeline in (e.g. `nids`):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r class_1_anomaly_detection/requirements-ml.txt
```

Without `torch` / `torch_geometric`, `export_pyg_graph` only writes `graph_tensors.npz` and GAD-NR training cannot run.

## Outputs

| Path | Role |
|------|------|
| `data/parquet/` | Working store (gitignored) |
| `output/rolling/anchor_YYYYMM/` | Network + rule metrics |
| `output/pyg/anchor_YYYYMM/` | PyG tensors |
| `output/ml/anchor_YYYYMM/` | GAD-NR scores |
| `output/ui/anchor_YYYYMM/` | Streamlit bundle |
| `exports/` | Next-year batch schema stubs |

## Spec

See `shared_docs/structured/class_1_anomaly_spec.md`.
UDI-centric GNN idea (not implemented): `notes/udi_centric_gnn_future.md`.
