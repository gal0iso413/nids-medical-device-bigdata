"""
PyGOD DOMINANT smoke test on the exported top7 supply graph.

Loads ``output/pyg/pyg_data.pt`` (or ``graph_tensors.npz`` fallback), trains
DOMINANT (reconstruction-based GNN anomaly detector), and writes ranked
entity scores plus a short comparison against Phase 1 BC baseline.

Run from repo root (after export_pyg_graph and requirements-ml.txt):
  python -m class_1_anomaly_detection.src.experiments.run_pygod_smoke
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_1_anomaly_detection.src.experiments.pygod_common import (
    ML_OUTPUT_DIR,
    load_baseline_tables,
    load_pyg_data,
    rank_overlap,
    save_model_scores,
    scores_to_frame,
    top_distributors,
)


def run_dominant_smoke(
    *,
    hid_dim: int = 64,
    num_layers: int = 2,
    epoch: int = 30,
    lr: float = 0.004,
    verbose: int = 1,
) -> pd.DataFrame:
    """Train DOMINANT and return entity-level anomaly scores."""
    try:
        from pygod.detector import DOMINANT
    except ImportError as exc:
        raise ImportError(
            "pygod not installed — pip install -r class_1_anomaly_detection/requirements-ml.txt"
        ) from exc

    data, entity_ids = load_pyg_data()
    baselines = load_baseline_tables()

    if verbose:
        print("=" * 70)
        print("  PyGOD DOMINANT smoke test")
        print("=" * 70)
        print(f"  Nodes     : {data.num_nodes:,}")
        print(f"  Edges     : {data.edge_index.shape[1]:,}")
        print(f"  Features  : {data.x.shape[1]}")
        print(f"  Epochs    : {epoch}")
        print(f"  Layers    : {num_layers}")
        print("  Training...")

    model = DOMINANT(
        hid_dim=hid_dim,
        num_layers=num_layers,
        epoch=epoch,
        lr=lr,
        gpu=-1,
        verbose=verbose,
    )
    model.fit(data)

    scores = np.asarray(model.decision_score_, dtype=np.float64)
    labels = np.asarray(model.label_, dtype=np.int64)
    df = scores_to_frame(entity_ids, scores, labels, "dominant", baselines)
    out_path = save_model_scores(df, "dominant")

    report = {
        "model": "DOMINANT",
        "nodes": int(data.num_nodes),
        "edges": int(data.edge_index.shape[1]),
        "feature_dim": int(data.x.shape[1]),
        "hid_dim": hid_dim,
        "num_layers": num_layers,
        "epoch": epoch,
        "flagged_nodes": int((labels == 1).sum()),
        "score_min": float(scores.min()),
        "score_max": float(scores.max()),
        "score_mean": float(scores.mean()),
        "top10_distributors": top_distributors(df, "dominant_score", n=10),
    }

    bc = baselines.get("bc")
    if bc is not None:
        bc_scores = bc.set_index("entity_id")["bc_score"]
        report["top50_overlap_dominant_vs_bc"] = rank_overlap(
            df.set_index("entity_id")["dominant_score"], bc_scores, k=50
        )
        report["top10_overlap_dominant_vs_bc"] = rank_overlap(
            df.set_index("entity_id")["dominant_score"], bc_scores, k=10
        )
        report["bc_high_risk_count"] = int(bc["high_risk"].fillna(False).sum())

    report_path = ML_OUTPUT_DIR / "dominant_smoke_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    if verbose:
        print("\n  Results")
        print(f"  Flagged nodes (DOMINANT) : {report['flagged_nodes']:,}")
        if bc is not None:
            print(
                f"  Top-10 overlap w/ BC   : "
                f"{report['top10_overlap_dominant_vs_bc']}/10"
            )
            print(
                f"  Top-50 overlap w/ BC   : "
                f"{report['top50_overlap_dominant_vs_bc']}/50"
            )
        print(f"  Scores saved             : {out_path.relative_to(_REPO_ROOT)}")
        print(f"  Report saved             : {report_path.relative_to(_REPO_ROOT)}")
        print("\n  Top 10 distributors by DOMINANT score:")
        for row in report["top10_distributors"]:
            bc_val = row.get("bc_score", "")
            bc_str = f"{float(bc_val):.4f}" if bc_val != "" else "n/a"
            print(
                f"    {row['entity_id']:20s}  score={row['dominant_score']:.6f}  "
                f"bc={bc_str}  {str(row.get('name', ''))[:40]}"
            )
        print("=" * 70)

    return df


if __name__ == "__main__":
    run_dominant_smoke()
