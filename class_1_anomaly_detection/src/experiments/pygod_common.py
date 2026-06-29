"""Shared helpers for PyGOD experiments on the top7 supply graph."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

OUTPUT_DIR = _REPO_ROOT / "class_1_anomaly_detection" / "output"
PYG_DIR = OUTPUT_DIR / "pyg"
ML_OUTPUT_DIR = OUTPUT_DIR / "ml"

MODEL_SLUGS = ("dominant", "anomalydae", "gadnr", "ocgnn", "isoforest")
RECONSTRUCTION_SLUGS = ("dominant", "anomalydae", "gadnr")
MEASURE_SLUGS = ("ocgnn", "isoforest")
DEFAULT_CONTAMINATION = 0.1

MODEL_LABELS = {
    "dominant": "DOMINANT",
    "anomalydae": "AnomalyDAE",
    "gadnr": "GAD-NR",
    "ocgnn": "OCGNN",
    "isoforest": "IsoForest (GAD-NR emb)",
}


def load_pyg_data():
    """Load PyG Data from .pt artifact, or rebuild from .npz."""
    pt_path = PYG_DIR / "pyg_data.pt"
    if pt_path.exists():
        import torch

        bundle = torch.load(pt_path, weights_only=False)
        return bundle["data"], bundle["entity_ids"]

    npz_path = PYG_DIR / "graph_tensors.npz"
    if not npz_path.exists():
        raise FileNotFoundError(
            "No pyg_data.pt or graph_tensors.npz — run export_pyg_graph first."
        )

    import torch
    from torch_geometric.data import Data

    arrays = np.load(npz_path)
    data = Data(
        x=torch.from_numpy(arrays["x"]),
        edge_index=torch.from_numpy(arrays["edge_index"]),
        edge_attr=torch.from_numpy(arrays["edge_attr"]),
    )
    data.num_nodes = int(arrays["x"].shape[0])

    index_map = pd.read_csv(PYG_DIR / "node_index_map.csv")
    entity_ids = index_map.sort_values("tensor_index")["entity_id"].astype(str).tolist()
    return data, entity_ids


def rank_overlap(rank_a: pd.Series, rank_b: pd.Series, k: int = 50) -> int:
    top_a = set(rank_a.nlargest(k).index)
    top_b = set(rank_b.nlargest(k).index)
    return len(top_a & top_b)


def spearman_corr(a: pd.Series, b: pd.Series) -> float | None:
    try:
        from scipy.stats import spearmanr

        valid = a.notna() & b.notna()
        if valid.sum() < 3:
            return None
        rho, _ = spearmanr(a[valid], b[valid])
        return float(rho) if not np.isnan(rho) else None
    except ImportError:
        return None


def load_baseline_tables() -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    nodes = OUTPUT_DIR / "network_nodes.csv"
    if nodes.exists():
        tables["nodes"] = pd.read_csv(nodes)
        tables["nodes"]["entity_id"] = tables["nodes"]["entity_id"].astype(str)

    bc_path = OUTPUT_DIR / "bc_per_entity.csv"
    if bc_path.exists():
        tables["bc"] = pd.read_csv(bc_path)
        tables["bc"]["entity_id"] = tables["bc"]["entity_id"].astype(str)

    pz_path = OUTPUT_DIR / "price_zscore_per_entity.csv"
    if pz_path.exists():
        pz = pd.read_csv(pz_path)
        pz["entity_id"] = pz["supplier_id"].astype(str)
        tables["price"] = pz

    lag_path = OUTPUT_DIR / "timelag_per_entity.csv"
    if lag_path.exists():
        lag = pd.read_csv(lag_path)
        lag["entity_id"] = lag["supplier_id"].astype(str)
        tables["timelag"] = lag

    return tables


def scores_to_frame(
    entity_ids: list[str],
    scores: np.ndarray,
    labels: np.ndarray,
    model_slug: str,
    baselines: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    score_col = f"{model_slug}_score"
    label_col = f"{model_slug}_label"
    rank_col = f"{model_slug}_rank"

    df = pd.DataFrame(
        {
            "tensor_index": range(len(entity_ids)),
            "entity_id": entity_ids,
            score_col: scores,
            label_col: labels,
        }
    )

    nodes = baselines.get("nodes")
    if nodes is not None:
        df = df.merge(nodes, on="entity_id", how="left")

    bc = baselines.get("bc")
    if bc is not None:
        df = df.merge(
            bc[["entity_id", "bc_score", "high_risk"]],
            on="entity_id",
            how="left",
        )
        df["bc_score"] = df["bc_score"].fillna(0.0)
        if "bc_rank" not in df.columns:
            df["bc_rank"] = df["bc_score"].rank(ascending=False, method="min").astype(int)

    df[rank_col] = df[score_col].rank(ascending=False, method="min").astype(int)
    return df


def save_model_scores(df: pd.DataFrame, model_slug: str) -> Path:
    ML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = ML_OUTPUT_DIR / f"entity_anomaly_scores_{model_slug}.csv"
    rank_col = f"{model_slug}_rank"
    df.sort_values(rank_col).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def top_distributors(df: pd.DataFrame, score_col: str, n: int = 10) -> list[dict[str, Any]]:
    if "node_type" not in df.columns:
        subset = df.nlargest(n, score_col)
    else:
        subset = df[df["node_type"] == "distributor"].nlargest(n, score_col)
    cols = ["entity_id", "name", score_col, "bc_score"]
    cols = [c for c in cols if c in subset.columns]
    return subset[cols].fillna("").to_dict(orient="records")


def apply_pygod_gadnr_patch() -> None:
    """
    PyGOD 1.1.0 passes ``tot_nodes`` into GCN via **kwargs; PyG 2.8+ rejects it.
    Strip the kwarg before backbone construction (upstream fix in pygod main).
    """
    from pygod.nn import gadnr as gadnr_nn

    if getattr(gadnr_nn.GADNRBase.__init__, "_nids_patched", False):
        return

    _orig_init = gadnr_nn.GADNRBase.__init__

    def _patched_init(self, *args, **kwargs):
        kwargs.pop("tot_nodes", None)
        return _orig_init(self, *args, **kwargs)

    _patched_init._nids_patched = True  # type: ignore[attr-defined]
    gadnr_nn.GADNRBase.__init__ = _patched_init


def labels_from_scores(scores: np.ndarray, contamination: float = DEFAULT_CONTAMINATION) -> np.ndarray:
    """Binary labels: top ``contamination`` fraction by score are anomalies (1)."""
    n = len(scores)
    n_out = max(1, int(round(contamination * n)))
    order = np.argsort(scores)[::-1]
    labels = np.zeros(n, dtype=np.int64)
    labels[order[:n_out]] = 1
    return labels


def load_saved_scores(model_slug: str) -> pd.DataFrame | None:
    path = ML_OUTPUT_DIR / f"entity_anomaly_scores_{model_slug}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["entity_id"] = df["entity_id"].astype(str)
    return df


def load_all_saved_frames(slugs: tuple[str, ...] | None = None) -> dict[str, pd.DataFrame]:
    """Load every per-model score CSV that exists on disk."""
    slugs = slugs or MODEL_SLUGS
    frames: dict[str, pd.DataFrame] = {}
    for slug in slugs:
        cached = load_saved_scores(slug)
        if cached is not None:
            frames[slug] = cached
    return frames
