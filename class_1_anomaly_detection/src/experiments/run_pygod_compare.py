"""
Compare PyGOD detectors on the top7 supply graph.

Runs reconstruction models (DOMINANT, AnomalyDAE, GAD-NR) plus anomaly-measure
models (OCGNN one-class, IsoForest on GAD-NR embeddings), writes per-model
score CSVs, a combined wide table, and a comparison report.

Run from repo root:
  python -m class_1_anomaly_detection.src.experiments.run_pygod_compare
  python -m class_1_anomaly_detection.src.experiments.run_pygod_compare --models ocgnn isoforest
  python -m class_1_anomaly_detection.src.experiments.run_pygod_compare --reuse
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_1_anomaly_detection.src.experiments.pygod_common import (
    DEFAULT_CONTAMINATION,
    ML_OUTPUT_DIR,
    MODEL_SLUGS,
    apply_pygod_gadnr_patch,
    labels_from_scores,
    load_all_saved_frames,
    load_baseline_tables,
    load_pyg_data,
    load_saved_scores,
    rank_overlap,
    save_model_scores,
    scores_to_frame,
    spearman_corr,
    top_distributors,
)

DEFAULT_EPOCH = 30
DEFAULT_HID_DIM = 64


def _require_pygod():
    try:
        from pygod.detector import AnomalyDAE, DOMINANT, GADNR, OCGNN  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "pygod not installed — pip install -r class_1_anomaly_detection/requirements-ml.txt"
        ) from exc


def _build_model(model_slug: str, *, epoch: int, hid_dim: int, verbose: int):
    from pygod.detector import AnomalyDAE, DOMINANT, GADNR, OCGNN

    common = dict(
        epoch=epoch,
        gpu=-1,
        verbose=verbose,
        contamination=DEFAULT_CONTAMINATION,
    )
    if model_slug == "dominant":
        return DOMINANT(hid_dim=hid_dim, num_layers=2, lr=0.004, **common)
    if model_slug == "anomalydae":
        return AnomalyDAE(emb_dim=hid_dim, hid_dim=hid_dim, lr=0.004, **common)
    if model_slug == "gadnr":
        return GADNR(hid_dim=hid_dim, num_layers=1, lr=0.01, **common)
    if model_slug == "ocgnn":
        return OCGNN(hid_dim=hid_dim, num_layers=2, lr=0.004, **common)
    raise ValueError(f"Unknown PyGOD model: {model_slug}")


def fit_isoforest(
    data,
    *,
    epoch: int,
    hid_dim: int,
    verbose: int,
    contamination: float = DEFAULT_CONTAMINATION,
) -> tuple[np.ndarray, np.ndarray, float]:
    """DIF-style: GAD-NR encoder embeddings + sklearn IsolationForest."""
    from pygod.detector import GADNR
    from sklearn.ensemble import IsolationForest

    apply_pygod_gadnr_patch()
    t0 = time.perf_counter()
    if verbose:
        print("  [ISOFORST] training GAD-NR encoder for embeddings...")
    encoder = GADNR(
        hid_dim=hid_dim,
        num_layers=1,
        lr=0.01,
        epoch=epoch,
        gpu=-1,
        verbose=verbose,
        save_emb=True,
        contamination=contamination,
    )
    encoder.fit(data)
    emb = encoder.emb
    if emb is None:
        raise RuntimeError("GAD-NR save_emb=True but embeddings are missing")
    emb_np = emb.detach().cpu().numpy() if hasattr(emb, "detach") else np.asarray(emb)

    if verbose:
        print("  [ISOFORST] fitting IsolationForest on embeddings...")
    iso = IsolationForest(contamination=contamination, random_state=42, n_jobs=-1)
    iso.fit(emb_np)
    scores = (-iso.decision_function(emb_np)).astype(np.float64)
    labels = labels_from_scores(scores, contamination)
    elapsed = time.perf_counter() - t0
    return scores, labels, elapsed


def fit_model(
    model_slug: str,
    data,
    *,
    epoch: int,
    hid_dim: int,
    verbose: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    if model_slug == "isoforest":
        return fit_isoforest(data, epoch=epoch, hid_dim=hid_dim, verbose=verbose)
    if model_slug == "gadnr":
        apply_pygod_gadnr_patch()
    t0 = time.perf_counter()
    model = _build_model(model_slug, epoch=epoch, hid_dim=hid_dim, verbose=verbose)
    model.fit(data)
    elapsed = time.perf_counter() - t0
    scores = np.asarray(model.decision_score_, dtype=np.float64)
    labels = np.asarray(model.label_, dtype=np.int64)
    return scores, labels, elapsed


def merge_combined(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    combined = None
    for slug, df in frames.items():
        score_col = f"{slug}_score"
        label_col = f"{slug}_label"
        rank_col = f"{slug}_rank"
        slim = df[
            ["entity_id", "tensor_index", score_col, label_col, rank_col]
            + [c for c in ("name", "node_type", "bc_score", "bc_rank", "high_risk") if c in df.columns]
        ].copy()
        if combined is None:
            combined = slim
        else:
            drop = [c for c in ("name", "node_type", "bc_score", "bc_rank", "high_risk") if c in slim.columns]
            combined = combined.merge(
                slim.drop(columns=drop, errors="ignore"),
                on=["entity_id", "tensor_index"],
                how="outer",
            )
    return combined.sort_values("entity_id") if combined is not None else pd.DataFrame()


def build_comparison_report(
    frames: dict[str, pd.DataFrame],
    timings: dict[str, float],
    *,
    epoch: int,
    hid_dim: int,
    data_meta: dict[str, int],
) -> dict[str, Any]:
    slugs = list(frames.keys())
    idx_frames = {s: df.set_index("entity_id") for s, df in frames.items()}

    report: dict[str, Any] = {
        "models": slugs,
        "epoch": epoch,
        "hid_dim": hid_dim,
        **data_meta,
        "train_seconds": {s: round(timings[s], 1) for s in slugs},
        "flagged_nodes": {
            s: int((idx_frames[s][f"{s}_label"] == 1).sum()) for s in slugs
        },
        "top10_distributors": {
            s: top_distributors(frames[s], f"{s}_score", n=10) for s in slugs
        },
    }

    overlap: dict[str, Any] = {}
    for i, a in enumerate(slugs):
        for b in slugs[i + 1 :]:
            key = f"{a}_vs_{b}"
            overlap[key] = {
                "top10": rank_overlap(
                    idx_frames[a][f"{a}_score"], idx_frames[b][f"{b}_score"], k=10
                ),
                "top50": rank_overlap(
                    idx_frames[a][f"{a}_score"], idx_frames[b][f"{b}_score"], k=50
                ),
                "spearman_all": spearman_corr(
                    idx_frames[a][f"{a}_score"], idx_frames[b][f"{b}_score"]
                ),
            }
            dist_a = frames[a][frames[a]["node_type"] == "distributor"].set_index("entity_id")
            dist_b = frames[b][frames[b]["node_type"] == "distributor"].set_index("entity_id")
            common = dist_a.index.intersection(dist_b.index)
            if len(common) >= 3:
                overlap[key]["spearman_distributors"] = spearman_corr(
                    dist_a.loc[common, f"{a}_score"],
                    dist_b.loc[common, f"{b}_score"],
                )

    report["model_pair_overlap"] = overlap

    bc_overlap: dict[str, Any] = {}
    baselines = load_baseline_tables()
    if "bc" in baselines:
        bc_scores = baselines["bc"].set_index("entity_id")["bc_score"]
        for s in slugs:
            bc_overlap[s] = {
                "top10_vs_bc": rank_overlap(idx_frames[s][f"{s}_score"], bc_scores, k=10),
                "top50_vs_bc": rank_overlap(idx_frames[s][f"{s}_score"], bc_scores, k=50),
                "spearman_vs_bc": spearman_corr(idx_frames[s][f"{s}_score"], bc_scores),
            }
    report["bc_overlap"] = bc_overlap

    price_overlap: dict[str, Any] = {}
    if "price" in baselines:
        pz = baselines["price"].set_index("entity_id")
        if "flag_rate" in pz.columns:
            for s in slugs:
                common = idx_frames[s].index.intersection(pz.index)
                if len(common) >= 3:
                    price_overlap[s] = {
                        "spearman_vs_price_flag_rate": spearman_corr(
                            idx_frames[s].loc[common, f"{s}_score"],
                            pz.loc[common, "flag_rate"],
                        )
                    }
    report["price_overlap"] = price_overlap

    return report


def run_compare(
    models: list[str] | None = None,
    *,
    epoch: int = DEFAULT_EPOCH,
    hid_dim: int = DEFAULT_HID_DIM,
    verbose: int = 1,
    reuse: bool = False,
) -> pd.DataFrame:
    _require_pygod()
    models = list(models or MODEL_SLUGS)

    data, entity_ids = load_pyg_data()
    baselines = load_baseline_tables()

    if verbose:
        print("=" * 70)
        print("  PyGOD model comparison")
        print("=" * 70)
        print(f"  Models    : {', '.join(models)}")
        print(f"  Nodes     : {data.num_nodes:,}")
        print(f"  Edges     : {data.edge_index.shape[1]:,}")
        print(f"  Features  : {data.x.shape[1]}")
        print(f"  Epochs    : {epoch}")
        print("=" * 70)

    frames: dict[str, pd.DataFrame] = {}
    timings: dict[str, float] = {}

    for slug in models:
        if reuse:
            cached = load_saved_scores(slug)
            if cached is not None:
                frames[slug] = cached
                timings[slug] = 0.0
                if verbose:
                    print(f"  [{slug.upper()}] reused {ML_OUTPUT_DIR.name}/entity_anomaly_scores_{slug}.csv")
                continue

        if verbose:
            print(f"\n  [{slug.upper()}] training...")
        scores, labels, elapsed = fit_model(
            slug, data, epoch=epoch, hid_dim=hid_dim, verbose=verbose
        )
        timings[slug] = elapsed
        df = scores_to_frame(entity_ids, scores, labels, slug, baselines)
        path = save_model_scores(df, slug)
        frames[slug] = df
        if verbose:
            flagged = int((labels == 1).sum())
            print(f"  [{slug.upper()}] done in {elapsed:.1f}s - flagged {flagged:,} nodes")
            print(f"  [{slug.upper()}] saved {path.relative_to(_REPO_ROOT)}")

    all_frames = load_all_saved_frames()
    all_frames.update(frames)
    all_timings = {slug: timings.get(slug, 0.0) for slug in all_frames}

    combined = merge_combined(all_frames)
    combined_path = ML_OUTPUT_DIR / "entity_anomaly_scores_combined.csv"
    ML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(combined_path, index=False, encoding="utf-8-sig")

    report = build_comparison_report(
        all_frames,
        all_timings,
        epoch=epoch,
        hid_dim=hid_dim,
        data_meta={
            "nodes": int(data.num_nodes),
            "edges": int(data.edge_index.shape[1]),
            "feature_dim": int(data.x.shape[1]),
        },
    )
    report_path = ML_OUTPUT_DIR / "pygod_model_comparison.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    if verbose:
        print("\n" + "=" * 70)
        print("  Comparison summary")
        print("=" * 70)
        for slug in all_frames:
            print(
                f"  {slug:12s}  train={all_timings[slug]:5.1f}s  "
                f"flagged={report['flagged_nodes'][slug]:,}"
            )
        print("\n  Pairwise top-10 overlap (distributors/entities):")
        for key, vals in report.get("model_pair_overlap", {}).items():
            print(f"    {key:25s}  {vals['top10']}/10")
        print("\n  vs BC top-10 overlap:")
        for slug, vals in report.get("bc_overlap", {}).items():
            print(f"    {slug:12s}  {vals['top10_vs_bc']}/10")
        print(f"\n  Combined scores : {combined_path.relative_to(_REPO_ROOT)}")
        print(f"  Report          : {report_path.relative_to(_REPO_ROOT)}")
        print("=" * 70)

    return combined


def main():
    parser = argparse.ArgumentParser(description="Compare PyGOD detectors on top7 graph")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(MODEL_SLUGS),
        default=list(MODEL_SLUGS),
        help="Models to train (default: all five)",
    )
    parser.add_argument("--epoch", type=int, default=DEFAULT_EPOCH)
    parser.add_argument("--hid-dim", type=int, default=DEFAULT_HID_DIM)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Skip training when entity_anomaly_scores_<model>.csv already exists",
    )
    args = parser.parse_args()
    run_compare(
        models=args.models,
        epoch=args.epoch,
        hid_dim=args.hid_dim,
        verbose=0 if args.quiet else 1,
        reuse=args.reuse,
    )


if __name__ == "__main__":
    main()
