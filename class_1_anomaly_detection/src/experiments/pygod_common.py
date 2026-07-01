"""Shared helpers for PyGOD experiments on the top7 supply graph."""
from __future__ import annotations

import hashlib
import json
import re
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
ROLLING_OUTPUT_ROOT = OUTPUT_DIR / "rolling"
ANCHOR_PREFIX = "anchor_"
EXPORT_REQUIRED_CSVS = (
    "network_nodes.csv",
    "network_edges.csv",
    "bc_per_entity.csv",
    "price_zscore_per_entity.csv",
    "timelag_per_entity.csv",
)

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


def _anchor_dir_name(anchor_month: str) -> str:
    return f"{ANCHOR_PREFIX}{anchor_month}"


def list_available_anchor_months() -> list[str]:
    if not ROLLING_OUTPUT_ROOT.exists():
        return []
    anchors: list[str] = []
    for p in ROLLING_OUTPUT_ROOT.iterdir():
        if not p.is_dir() or not p.name.startswith(ANCHOR_PREFIX):
            continue
        anchor = p.name.removeprefix(ANCHOR_PREFIX)
        if re.fullmatch(r"\d{6}", anchor):
            anchors.append(anchor)
    return sorted(set(anchors))


def _anchor_has_required_files(base_dir: Path, filenames: tuple[str, ...]) -> bool:
    return all((base_dir / name).exists() for name in filenames)


def list_export_ready_anchor_months() -> list[str]:
    """Anchors with required rolling CSVs for PyG export."""
    ready: list[str] = []
    for anchor in list_available_anchor_months():
        base = ROLLING_OUTPUT_ROOT / _anchor_dir_name(anchor)
        if _anchor_has_required_files(base, EXPORT_REQUIRED_CSVS):
            ready.append(anchor)
    return sorted(set(ready))


def list_compare_ready_anchor_months() -> list[str]:
    """Anchors with rolling CSVs and PyG graph artifact ready."""
    ready: list[str] = []
    for anchor in list_export_ready_anchor_months():
        pyg_dir = PYG_DIR / _anchor_dir_name(anchor)
        if (pyg_dir / "pyg_data.pt").exists() or (pyg_dir / "graph_tensors.npz").exists():
            ready.append(anchor)
    return sorted(set(ready))


def list_evaluation_ready_anchor_months() -> list[str]:
    """Anchors with combined GNN scores and rolling baseline files."""
    ready: list[str] = []
    for anchor in list_available_anchor_months():
        rolling_dir = ROLLING_OUTPUT_ROOT / _anchor_dir_name(anchor)
        ml_dir = ML_OUTPUT_DIR / _anchor_dir_name(anchor)
        if not _anchor_has_required_files(rolling_dir, ("network_nodes.csv",)):
            continue
        if not (ml_dir / "entity_anomaly_scores_combined.csv").exists():
            continue
        ready.append(anchor)
    return sorted(set(ready))


def normalize_anchor_month(anchor_month: str | None) -> str:
    """
    Normalize anchor month to YYYYMM.

    If not provided, resolve to latest available anchor under output/rolling.
    """
    if anchor_month is not None:
        anchor = str(anchor_month).strip()
        if not re.fullmatch(r"\d{6}", anchor):
            raise ValueError(f"Invalid anchor month '{anchor_month}'. Expected YYYYMM.")
        return anchor
    anchors = list_available_anchor_months()
    if not anchors:
        raise ValueError(
            "Anchor month was not provided and no anchor outputs exist yet. "
            "Run run_graph_eda with --anchor-month first."
        )
    return anchors[-1]


def rolling_output_dir(anchor_month: str | None) -> Path:
    anchor = normalize_anchor_month(anchor_month)
    return ROLLING_OUTPUT_ROOT / _anchor_dir_name(anchor)


def rolling_ml_dir(anchor_month: str | None) -> Path:
    anchor = normalize_anchor_month(anchor_month)
    return ML_OUTPUT_DIR / _anchor_dir_name(anchor)


def rolling_pyg_dir(anchor_month: str | None) -> Path:
    anchor = normalize_anchor_month(anchor_month)
    return PYG_DIR / _anchor_dir_name(anchor)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def build_run_fingerprint(
    *,
    anchor_month: str,
    window_months: list[str],
    models: list[str],
    epoch: int,
    hid_dim: int,
    contamination: float,
    feature_signature: str,
    input_signature: str,
    code_version: str,
) -> dict[str, Any]:
    payload = {
        "anchor_month": anchor_month,
        "window_months": list(window_months),
        "models": sorted(models),
        "epoch": int(epoch),
        "hid_dim": int(hid_dim),
        "contamination": float(contamination),
        "feature_signature": feature_signature,
        "input_signature": input_signature,
        "code_version": code_version,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return {"hash": digest, "payload": payload}


def is_reuse_valid(meta_path: Path, fingerprint: dict[str, Any]) -> bool:
    meta = read_json(meta_path)
    if not meta:
        return False
    cached = meta.get("fingerprint", {})
    return bool(cached.get("hash")) and cached.get("hash") == fingerprint.get("hash")


def load_pyg_data(anchor_month: str | None = None):
    """Load PyG Data from .pt artifact, or rebuild from .npz."""
    base = rolling_pyg_dir(anchor_month) if anchor_month is not None else PYG_DIR
    pt_path = base / "pyg_data.pt"
    if pt_path.exists():
        import torch

        bundle = torch.load(pt_path, weights_only=False)
        return bundle["data"], bundle["entity_ids"]

    npz_path = base / "graph_tensors.npz"
    if not npz_path.exists():
        raise FileNotFoundError(
            f"No pyg_data.pt or graph_tensors.npz for anchor={anchor_month} — "
            "run export_pyg_graph first."
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

    index_map = pd.read_csv(base / "node_index_map.csv")
    entity_ids = index_map.sort_values("tensor_index")["entity_id"].astype(str).tolist()
    return data, entity_ids


def load_monthly_pyg_data(month: str, anchor_month: str | None = None):
    """Load fixed edge_index/x from main pyg_data.pt and monthly edge_attr."""
    import torch

    data, entity_ids = load_pyg_data(anchor_month=anchor_month)
    base = rolling_pyg_dir(anchor_month) if anchor_month is not None else PYG_DIR
    monthly_path = base / f"pyg_monthly_{month}.npz"
    if not monthly_path.exists():
        raise FileNotFoundError(
            f"No monthly data for {month} — run run_graph_eda or export_monthly_edge_attrs."
        )
    arrays = np.load(monthly_path)
    data_monthly = data.clone()
    data_monthly.edge_attr = torch.from_numpy(arrays["edge_attr_month"])
    return data_monthly, entity_ids


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


def load_baseline_tables(anchor_month: str | None = None) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    base = rolling_output_dir(anchor_month) if anchor_month is not None else OUTPUT_DIR
    nodes = base / "network_nodes.csv"
    if nodes.exists():
        tables["nodes"] = pd.read_csv(nodes)
        tables["nodes"]["entity_id"] = tables["nodes"]["entity_id"].astype(str)

    bc_path = base / "bc_per_entity.csv"
    if bc_path.exists():
        tables["bc"] = pd.read_csv(bc_path)
        tables["bc"]["entity_id"] = tables["bc"]["entity_id"].astype(str)

    pz_path = base / "price_zscore_per_entity.csv"
    if pz_path.exists():
        pz = pd.read_csv(pz_path)
        pz["entity_id"] = pz["supplier_id"].astype(str)
        tables["price"] = pz

    lag_path = base / "timelag_per_entity.csv"
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


def save_model_scores(
    df: pd.DataFrame,
    model_slug: str,
    *,
    anchor_month: str | None = None,
) -> Path:
    out_dir = rolling_ml_dir(anchor_month) if anchor_month is not None else ML_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"entity_anomaly_scores_{model_slug}.csv"
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


def load_saved_scores(
    model_slug: str,
    *,
    anchor_month: str | None = None,
) -> pd.DataFrame | None:
    in_dir = rolling_ml_dir(anchor_month) if anchor_month is not None else ML_OUTPUT_DIR
    path = in_dir / f"entity_anomaly_scores_{model_slug}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["entity_id"] = df["entity_id"].astype(str)
    return df


def load_all_saved_frames(
    slugs: tuple[str, ...] | None = None,
    *,
    anchor_month: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Load every per-model score CSV that exists on disk."""
    slugs = slugs or MODEL_SLUGS
    frames: dict[str, pd.DataFrame] = {}
    for slug in slugs:
        cached = load_saved_scores(slug, anchor_month=anchor_month)
        if cached is not None:
            frames[slug] = cached
    return frames
