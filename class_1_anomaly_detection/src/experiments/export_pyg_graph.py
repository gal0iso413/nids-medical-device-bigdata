"""
Export top7 supply-network CSV artifacts to a PyTorch Geometric Data object.

Reads Phase 1 outputs from ``class_1_anomaly_detection/output/``:
  - network_nodes.csv, network_edges.csv
  - bc_per_entity.csv, price_zscore_per_entity.csv, timelag_per_entity.csv

Writes to ``class_1_anomaly_detection/output/pyg/``:
  - pyg_data.pt          (when torch + torch_geometric are installed)
  - graph_tensors.npz    (numpy fallback — same tensors)
  - node_index_map.csv   (entity_id ↔ tensor row)
  - feature_columns.json (column order for x)
  - pyg_sanity_report.json

Run from repo root:
  python -m class_1_anomaly_detection.src.experiments.export_pyg_graph --anchor-month 202605
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

OUTPUT_DIR = _REPO_ROOT / "class_1_anomaly_detection" / "output"
PYG_DIR = OUTPUT_DIR / "pyg"

from class_1_anomaly_detection.src.experiments.pygod_common import (
    list_available_anchor_months,
    list_export_ready_anchor_months,
    normalize_anchor_month,
    write_json,
    rolling_output_dir,
    rolling_pyg_dir,
)

NODE_TYPE_VALUES = (
    "manufacturer",
    "importer",
    "distributor",
    "hospital",
    "other",
)

LOCATION_CODE_VALUES = (
    "11", "26", "27", "28", "29", "30", "31", "36",
    "41", "42", "43", "44", "45", "46", "47", "48", "50",
)

CONTINUOUS_FEATURES = [
    "in_degree",
    "out_degree",
    "in_weight_log",
    "out_weight_log",
    "in_tx_log",
    "out_tx_log",
    "bc_score",
    "avg_udi_count_out",
    "avg_udi_count_in",
    "max_device_class_out",
    "max_device_class_in",
    "zero_price_edge_rate",
    "traceable_edge_rate",
    "reimbursable_edge_rate",
    "price_flag_rate",
    "price_median_z",
    "price_max_z",
    "timelag_median_log",
    "timelag_max_log",
    "backdated_count_log",
]


def _load_csv(name: str, *, base_dir: Path = OUTPUT_DIR) -> pd.DataFrame:
    path = base_dir / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path.relative_to(_REPO_ROOT)} — run run_graph_eda.py first."
        )
    return pd.read_csv(path)


def _load_window_months(base_dir: Path) -> list[str]:
    manifest = base_dir / "manifest.json"
    if not manifest.exists():
        return []
    try:
        with open(manifest, encoding="utf-8") as f:
            payload = json.load(f)
        vals = payload.get("window_months", [])
        return [str(v) for v in vals if str(v).strip()]
    except Exception:
        return []


def _log1p_nonneg(series: pd.Series) -> pd.Series:
    return np.log1p(series.fillna(0).clip(lower=0))


def _degree_features(edges: pd.DataFrame, node_ids: list[str]) -> pd.DataFrame:
    """Aggregate directed degree, weight sums, and edge-risk signals per entity."""
    idx = {eid: i for i, eid in enumerate(node_ids)}
    n = len(node_ids)

    in_deg = np.zeros(n, dtype=np.float64)
    out_deg = np.zeros(n, dtype=np.float64)
    in_weight = np.zeros(n, dtype=np.float64)
    out_weight = np.zeros(n, dtype=np.float64)
    in_tx = np.zeros(n, dtype=np.float64)
    out_tx = np.zeros(n, dtype=np.float64)

    out_udi_sum = np.zeros(n, dtype=np.float64)
    in_udi_sum = np.zeros(n, dtype=np.float64)
    out_max_class = np.zeros(n, dtype=np.float64)
    in_max_class = np.zeros(n, dtype=np.float64)
    out_zero_price = np.zeros(n, dtype=np.float64)
    in_zero_price = np.zeros(n, dtype=np.float64)
    out_traceable = np.zeros(n, dtype=np.float64)
    in_traceable = np.zeros(n, dtype=np.float64)
    out_reimbursable = np.zeros(n, dtype=np.float64)
    in_reimbursable = np.zeros(n, dtype=np.float64)

    def _f(row, col: str, default: float = 0.0) -> float:
        return float(getattr(row, col, default)) if hasattr(row, col) and pd.notna(getattr(row, col, default)) else default

    for row in edges.itertuples(index=False):
        src = str(row.src)
        dst = str(row.dst)
        weight = float(row.weight) if pd.notna(row.weight) else 0.0
        tx_count = float(row.tx_count) if pd.notna(row.tx_count) else 0.0
        udi_count = _f(row, "unique_udi_count")
        max_class = _f(row, "max_device_class")
        zero_price = _f(row, "has_zero_price")
        traceable = _f(row, "has_traceable")
        reimbursable = _f(row, "has_reimbursable")

        if src in idx:
            si = idx[src]
            out_deg[si] += 1
            out_weight[si] += max(weight, 0.0)
            out_tx[si] += max(tx_count, 0.0)
            out_udi_sum[si] += udi_count
            out_max_class[si] = max(out_max_class[si], max_class)
            out_zero_price[si] += zero_price
            out_traceable[si] += traceable
            out_reimbursable[si] += reimbursable
        if dst in idx:
            di = idx[dst]
            in_deg[di] += 1
            in_weight[di] += max(weight, 0.0)
            in_tx[di] += max(tx_count, 0.0)
            in_udi_sum[di] += udi_count
            in_max_class[di] = max(in_max_class[di], max_class)
            in_zero_price[di] += zero_price
            in_traceable[di] += traceable
            in_reimbursable[di] += reimbursable

    out_deg_safe = np.maximum(out_deg, 1.0)
    in_deg_safe = np.maximum(in_deg, 1.0)
    total_edge_deg = np.maximum(in_deg + out_deg, 1.0)

    return pd.DataFrame(
        {
            "entity_id": node_ids,
            "in_degree": in_deg,
            "out_degree": out_deg,
            "in_weight_log": _log1p_nonneg(pd.Series(in_weight)),
            "out_weight_log": _log1p_nonneg(pd.Series(out_weight)),
            "in_tx_log": _log1p_nonneg(pd.Series(in_tx)),
            "out_tx_log": _log1p_nonneg(pd.Series(out_tx)),
            "avg_udi_count_out": out_udi_sum / out_deg_safe,
            "avg_udi_count_in": in_udi_sum / in_deg_safe,
            "max_device_class_out": out_max_class,
            "max_device_class_in": in_max_class,
            "zero_price_edge_rate": (in_zero_price + out_zero_price) / total_edge_deg,
            "traceable_edge_rate": (in_traceable + out_traceable) / total_edge_deg,
            "reimbursable_edge_rate": (in_reimbursable + out_reimbursable) / total_edge_deg,
        }
    )


def _one_hot_node_types(node_types: pd.Series) -> pd.DataFrame:
    normalized = node_types.fillna("other").astype(str).str.strip().str.lower()
    normalized = normalized.replace("unknown", "other")
    normalized = normalized.where(normalized.isin(NODE_TYPE_VALUES), "other")
    return pd.get_dummies(normalized, prefix="type")


def _one_hot_location(locations: pd.Series) -> pd.DataFrame:
    normalized = (
        locations.fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )
    normalized = normalized.where(normalized.isin(LOCATION_CODE_VALUES), "other")
    cols = [f"loc_{code}" for code in LOCATION_CODE_VALUES] + ["loc_other"]
    dummies = pd.get_dummies(normalized, prefix="loc")
    return dummies.reindex(columns=cols, fill_value=0)


def build_node_features(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    bc: pd.DataFrame,
    price: pd.DataFrame,
    timelag: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Join graph topology metrics with Phase 1 entity-level indicators."""
    node_ids = nodes["entity_id"].astype(str).tolist()
    features = nodes[["entity_id", "node_type"]].copy()
    features["entity_id"] = features["entity_id"].astype(str)
    if "location" in nodes.columns:
        features = features.merge(
            nodes[["entity_id", "location"]].assign(
                entity_id=nodes["entity_id"].astype(str)
            ),
            on="entity_id",
            how="left",
        )
    else:
        features["location"] = ""

    features = features.merge(_degree_features(edges, node_ids), on="entity_id", how="left")

    bc_cols = bc.rename(columns={"entity_id": "entity_id"}).copy()
    bc_cols["entity_id"] = bc_cols["entity_id"].astype(str)
    features = features.merge(
        bc_cols[["entity_id", "bc_score", "in_degree", "out_degree"]].rename(
            columns={"in_degree": "bc_in_degree", "out_degree": "bc_out_degree"}
        ),
        on="entity_id",
        how="left",
    )
    # Prefer edge-derived degrees; keep BC table degrees only as fallback.
    features["in_degree"] = features["in_degree"].fillna(features["bc_in_degree"]).fillna(0)
    features["out_degree"] = features["out_degree"].fillna(features["bc_out_degree"]).fillna(0)
    features.drop(columns=["bc_in_degree", "bc_out_degree"], inplace=True)
    features["bc_score"] = features["bc_score"].fillna(0.0)

    price_cols = price.rename(columns={"supplier_id": "entity_id"}).copy()
    price_cols["entity_id"] = price_cols["entity_id"].astype(str)
    features = features.merge(
        price_cols[
            ["entity_id", "flag_rate", "median_zscore", "max_zscore"]
        ].rename(
            columns={
                "flag_rate": "price_flag_rate",
                "median_zscore": "price_median_z",
                "max_zscore": "price_max_z",
            }
        ),
        on="entity_id",
        how="left",
    )
    for col in ("price_flag_rate", "price_median_z", "price_max_z"):
        features[col] = features[col].fillna(0.0)

    lag_cols = timelag.rename(columns={"supplier_id": "entity_id"}).copy()
    lag_cols["entity_id"] = lag_cols["entity_id"].astype(str)
    lag_merge_cols = ["entity_id", "median_lag_days", "max_lag_days"]
    if "backdated_count" in lag_cols.columns:
        lag_merge_cols.append("backdated_count")
    features = features.merge(
        lag_cols[lag_merge_cols],
        on="entity_id",
        how="left",
    )
    features["timelag_median_log"] = _log1p_nonneg(features["median_lag_days"])
    features["timelag_max_log"] = _log1p_nonneg(features["max_lag_days"])
    features["backdated_count_log"] = _log1p_nonneg(
        features["backdated_count"] if "backdated_count" in features.columns else 0
    )
    drop_cols = ["median_lag_days", "max_lag_days"]
    if "backdated_count" in features.columns:
        drop_cols.append("backdated_count")
    features.drop(columns=drop_cols, inplace=True)

    type_dummies = _one_hot_node_types(features["node_type"])
    type_dummies.index = features.index
    loc_dummies = _one_hot_location(features["location"])
    loc_dummies.index = features.index
    features = pd.concat(
        [
            features.drop(columns=["node_type", "location"]),
            type_dummies,
            loc_dummies,
        ],
        axis=1,
    )

    feature_names = CONTINUOUS_FEATURES + sorted(
        c for c in features.columns if c.startswith("type_") or c.startswith("loc_")
    )
    return features, feature_names


_BOOL_MAP: dict[Any, float] = {
    "True": 1.0,
    "False": 0.0,
    "true": 1.0,
    "false": 0.0,
    True: 1.0,
    False: 0.0,
    1: 1.0,
    0: 0.0,
    "1": 1.0,
    "0": 0.0,
}


def _b(row, col: str) -> float:
    val = getattr(row, col, False)
    if pd.isna(val):
        return 0.0
    return _BOOL_MAP.get(val, 1.0 if bool(val) else 0.0)


def _edge_attr_vector(
    *,
    weight: float,
    tx_count: float,
    has_zero_price: bool,
    udi_count: float,
    has_traceable: bool,
    has_reimbursable: bool,
    max_class: float,
) -> list[float]:
    return [
        float(np.log1p(max(weight, 0.0))),
        float(np.log1p(max(tx_count, 0.0))),
        float(has_zero_price),
        float(np.log1p(max(udi_count, 0.0))),
        float(has_traceable),
        float(has_reimbursable),
        max_class / 4.0,
    ]


def build_edge_tensors(
    edges: pd.DataFrame,
    entity_to_idx: dict[str, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Build directed edge_index [2, E] and edge_attr [E, 7]."""
    src_idx: list[int] = []
    dst_idx: list[int] = []
    attrs: list[list[float]] = []

    for row in edges.itertuples(index=False):
        src = str(row.src)
        dst = str(row.dst)
        if src not in entity_to_idx or dst not in entity_to_idx:
            continue
        weight = float(row.weight) if pd.notna(row.weight) else 0.0
        tx_count = float(row.tx_count) if pd.notna(row.tx_count) else 0.0
        udi_count = float(getattr(row, "unique_udi_count", 0) or 0)
        max_class = float(getattr(row, "max_device_class", 0) or 0)
        src_idx.append(entity_to_idx[src])
        dst_idx.append(entity_to_idx[dst])
        attrs.append(
            _edge_attr_vector(
                weight=weight,
                tx_count=tx_count,
                has_zero_price=bool(_b(row, "has_zero_price")),
                udi_count=udi_count,
                has_traceable=bool(_b(row, "has_traceable")),
                has_reimbursable=bool(_b(row, "has_reimbursable")),
                max_class=max_class,
            )
        )

    if not src_idx:
        raise ValueError("No valid edges after indexing — check node/edge CSV alignment.")

    edge_index = np.array([src_idx, dst_idx], dtype=np.int64)
    edge_attr = np.array(attrs, dtype=np.float32)
    return edge_index, edge_attr


def _largest_wcc_stats(entity_ids: list[str], edge_index: np.ndarray) -> dict:
    G = nx.DiGraph()
    G.add_nodes_from(range(len(entity_ids)))
    for i in range(edge_index.shape[1]):
        G.add_edge(int(edge_index[0, i]), int(edge_index[1, i]))
    wccs = list(nx.weakly_connected_components(G))
    largest = max(wccs, key=len)
    return {
        "weakly_connected_components": len(wccs),
        "largest_wcc_nodes": len(largest),
        "largest_wcc_fraction": round(len(largest) / max(len(entity_ids), 1), 4),
    }


def _top_k_overlap(
    features: pd.DataFrame,
    col_a: str,
    col_b: str,
    k: int = 10,
) -> dict:
    top_a = set(features.nlargest(k, col_a)["entity_id"])
    top_b = set(features.nlargest(k, col_b)["entity_id"])
    overlap = top_a & top_b
    return {
        "metric_a": col_a,
        "metric_b": col_b,
        "k": k,
        "overlap_count": len(overlap),
        "overlap_entity_ids": sorted(overlap),
    }


def build_sanity_report(
    features: pd.DataFrame,
    edge_index: np.ndarray,
    feature_names: list[str],
    x: np.ndarray,
) -> dict:
    wcc = _largest_wcc_stats(features["entity_id"].tolist(), edge_index)
    node_types = {
        c.removeprefix("type_"): int(features[c].sum())
        for c in feature_names
        if c.startswith("type_")
    }
    return {
        "nodes": len(features),
        "edges": int(edge_index.shape[1]),
        "feature_dim": int(x.shape[1]),
        "feature_columns": feature_names,
        "node_type_counts": node_types,
        "continuous_feature_means": {
            name: round(float(x[:, feature_names.index(name)].mean()), 4)
            for name in CONTINUOUS_FEATURES
            if name in feature_names
        },
        "price_feature_nonzero_rate": round(
            float((features["price_median_z"] != 0).mean()), 4
        ),
        "timelag_feature_nonzero_rate": round(
            float((features["timelag_median_log"] != 0).mean()), 4
        ),
        "bc_nonzero_rate": round(float((features["bc_score"] > 0).mean()), 4),
        **wcc,
        "top10_overlap_degree_vs_bc": _top_k_overlap(
            features, "out_degree", "bc_score", k=10
        ),
        "top10_overlap_in_degree_vs_bc": _top_k_overlap(
            features, "in_degree", "bc_score", k=10
        ),
    }


def export_pyg_graph(
    *,
    anchor_month: str | None = None,
    verbose: bool = True,
) -> Path:
    """Load CSV artifacts, build tensors, save PyG-ready outputs."""
    anchor = normalize_anchor_month(anchor_month) if anchor_month is not None else None
    data_dir = rolling_output_dir(anchor) if anchor is not None else OUTPUT_DIR
    out_dir = rolling_pyg_dir(anchor) if anchor is not None else PYG_DIR

    nodes = _load_csv("network_nodes", base_dir=data_dir)
    edges = _load_csv("network_edges", base_dir=data_dir)
    bc = _load_csv("bc_per_entity", base_dir=data_dir)
    price = _load_csv("price_zscore_per_entity", base_dir=data_dir)
    timelag = _load_csv("timelag_per_entity", base_dir=data_dir)

    features, feature_names = build_node_features(nodes, edges, bc, price, timelag)
    entity_ids = features["entity_id"].astype(str).tolist()
    entity_to_idx = {eid: i for i, eid in enumerate(entity_ids)}

    edge_index, edge_attr = build_edge_tensors(edges, entity_to_idx)

    x_raw = features[feature_names].to_numpy(dtype=np.float32)
    scaler = StandardScaler()
    x = scaler.fit_transform(x_raw).astype(np.float32)

    sanity = build_sanity_report(features, edge_index, feature_names, x)

    out_dir.mkdir(parents=True, exist_ok=True)

    index_map = features[["entity_id"]].copy()
    index_map.insert(0, "tensor_index", range(len(index_map)))
    index_map.to_csv(out_dir / "node_index_map.csv", index=False, encoding="utf-8-sig")

    with open(out_dir / "feature_columns.json", "w", encoding="utf-8") as f:
        json.dump(feature_names, f, indent=2)

    np.savez(
        out_dir / "graph_tensors.npz",
        x=x,
        edge_index=edge_index,
        edge_attr=edge_attr,
    )

    pt_path = out_dir / "pyg_data.pt"
    try:
        import torch
        from torch_geometric.data import Data

        data = Data(
            x=torch.from_numpy(x),
            edge_index=torch.from_numpy(edge_index),
            edge_attr=torch.from_numpy(edge_attr),
        )
        data.num_nodes = len(entity_ids)
        torch.save(
            {
                "data": data,
                "entity_ids": entity_ids,
                "feature_names": feature_names,
                "scaler_mean": scaler.mean_.tolist(),
                "scaler_scale": scaler.scale_.tolist(),
            },
            pt_path,
        )
        sanity["pyg_data_pt"] = str(pt_path.relative_to(_REPO_ROOT)).replace("\\", "/")
    except ImportError:
        sanity["pyg_data_pt"] = None
        sanity["pyg_install_hint"] = (
            "pip install -r class_1_anomaly_detection/requirements-ml.txt"
        )
        if verbose:
            print(
                "  [note] torch/torch_geometric not installed - saved graph_tensors.npz only."
            )

    with open(out_dir / "pyg_sanity_report.json", "w", encoding="utf-8") as f:
        json.dump(sanity, f, indent=2, ensure_ascii=False)

    metadata = {
        "anchor_month": anchor,
        "window_months": _load_window_months(data_dir),
        "input_dir": str(data_dir.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "output_dir": str(out_dir.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "nodes": int(len(features)),
        "edges": int(edge_index.shape[1]),
        "feature_dim": int(x.shape[1]),
        "feature_signature": hashlib.sha256(
            json.dumps(feature_names, ensure_ascii=True).encode("utf-8")
        ).hexdigest(),
    }
    with open(out_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    if verbose:
        print("=" * 70)
        print("  PyG graph export - sanity summary")
        print("=" * 70)
        print(f"  Nodes              : {sanity['nodes']:,}")
        print(f"  Edges              : {sanity['edges']:,}")
        print(f"  Feature dim        : {sanity['feature_dim']}")
        print(f"  WCC                : {sanity['weakly_connected_components']}")
        print(
            f"  Largest WCC        : {sanity['largest_wcc_nodes']:,} nodes "
            f"({sanity['largest_wcc_fraction']:.1%})"
        )
        print(f"  Node types         : {sanity['node_type_counts']}")
        print(
            f"  Top-10 overlap     : out_degree vs bc_score = "
            f"{sanity['top10_overlap_degree_vs_bc']['overlap_count']}/10"
        )
        print(f"  Output dir         : {out_dir.relative_to(_REPO_ROOT)}")
        if sanity.get("pyg_data_pt"):
            print(f"  PyG artifact       : {sanity['pyg_data_pt']}")
        else:
            print(f"  Install hint       : {sanity.get('pyg_install_hint')}")
        if anchor is not None:
            print(f"  Anchor month       : {anchor}")
        print("=" * 70)

    return out_dir


def export_pyg_graph_all_anchors(*, verbose: bool = True) -> dict[str, Any]:
    """
    Export PyG graph artifacts for every export-ready anchor.

    Returns a summary dictionary and writes it to output/pyg/.
    """
    discovered = list_available_anchor_months()
    ready = list_export_ready_anchor_months()
    skipped = [a for a in discovered if a not in set(ready)]
    successes: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []

    if verbose:
        print("=" * 70)
        print("  PyG graph export - all anchors")
        print("=" * 70)
        if discovered:
            print(f"  Discovered anchors : {len(discovered)} ({discovered[0]} ~ {discovered[-1]})")
        else:
            print("  Discovered anchors : 0")
        print(f"  Export-ready       : {len(ready)}")
        print(f"  Skipped (missing rolling CSVs): {len(skipped)}")

    for anchor in ready:
        try:
            if verbose:
                print(f"\n  [anchor {anchor}] exporting...")
            out = export_pyg_graph(anchor_month=anchor, verbose=verbose)
            successes.append(
                {
                    "anchor_month": anchor,
                    "output_dir": str(out.relative_to(_REPO_ROOT)).replace("\\", "/"),
                }
            )
        except Exception as exc:
            failures.append({"anchor_month": anchor, "error": str(exc)})
            if verbose:
                print(f"  [anchor {anchor}] failed: {exc}")

    summary: dict[str, Any] = {
        "mode": "all_anchors",
        "discovered_anchors": discovered,
        "export_ready_anchors": ready,
        "skipped_missing_inputs": skipped,
        "successes": successes,
        "failures": failures,
    }
    summary_path = PYG_DIR / "export_all_anchors_summary.json"
    write_json(summary_path, summary)
    if verbose:
        print("\n" + "=" * 70)
        print("  All-anchor export summary")
        print("=" * 70)
        print(f"  Successes: {len(successes)}")
        print(f"  Failures : {len(failures)}")
        print(f"  Summary  : {summary_path.relative_to(_REPO_ROOT)}")
        print("=" * 70)
    return summary


def export_monthly_edge_attrs(
    supply: pd.DataFrame,
    edges: pd.DataFrame,
    *,
    months: list[str] | None = None,
    target_dir: Path | None = None,
    verbose: bool = True,
) -> list[dict]:
    """
    Export per-month edge_attr tensors aligned to the main graph edge skeleton.

    Each ``pyg_monthly_{YYYYMM}.npz`` contains ``edge_attr_month`` [E, 7] where
    edges absent in that month are zero vectors.
    """
    from class_1_anomaly_detection.src.graph.build_network import build_month_edge_aggregates
    from class_1_anomaly_detection.src.ingest.keys import COL_BASE_MONTH

    if edges.empty or COL_BASE_MONTH not in supply.columns:
        if verbose:
            print("  [SKIP] No edges or base-month column — monthly export skipped.")
        return []

    if "product_key" not in edges.columns:
        if verbose:
            print("  [SKIP] network_edges.csv missing product_key — re-run graph EDA.")
        return []

    out_dir = target_dir or PYG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    skeleton = edges[["src", "dst", "product_key"]].astype(str)
    edge_keys = list(zip(skeleton["src"], skeleton["dst"], skeleton["product_key"]))
    edge_to_idx = {k: i for i, k in enumerate(edge_keys)}
    n_edges = len(edge_keys)

    month_values = (
        [str(m).strip() for m in months]
        if months is not None
        else sorted(supply[COL_BASE_MONTH].dropna().astype(str).str.strip().unique())
    )
    manifest: list[dict] = []

    for month in month_values:
        month_table = build_month_edge_aggregates(supply, month)
        attrs = np.zeros((n_edges, 7), dtype=np.float32)
        active = 0

        if not month_table.empty:
            for rec in month_table.to_dict("records"):
                key = (str(rec["src"]), str(rec["dst"]), str(rec["_product_key"]))
                idx = edge_to_idx.get(key)
                if idx is None:
                    continue
                active += 1
                attrs[idx] = _edge_attr_vector(
                    weight=float(rec["weight"]),
                    tx_count=float(rec["tx_count"]),
                    has_zero_price=bool(rec["has_zero_price"]),
                    udi_count=float(rec["unique_udi_count"]),
                    has_traceable=bool(rec["has_traceable"]),
                    has_reimbursable=bool(rec["has_reimbursable"]),
                    max_class=float(rec["max_device_class"]),
                )

        out_path = out_dir / f"pyg_monthly_{month}.npz"
        np.savez(out_path, edge_attr_month=attrs, month=np.array(month))
        manifest.append({
            "month": month,
            "path": str(out_path.relative_to(_REPO_ROOT)).replace("\\", "/"),
            "active_edges": active,
            "total_edges": n_edges,
        })

    manifest_path = out_dir / "monthly_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if verbose:
        print(f"  [saved] {len(manifest)} monthly files → {out_dir.relative_to(_REPO_ROOT)}")

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export PyG graph artifacts")
    parser.add_argument("--anchor-month", type=str, default=None, help="Anchor month YYYYMM")
    parser.add_argument(
        "--all-anchors",
        action="store_true",
        help="Export PyG artifacts for every export-ready anchor.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.all_anchors and args.anchor_month is not None:
        parser.error("Use either --anchor-month or --all-anchors, not both.")
    if args.all_anchors:
        export_pyg_graph_all_anchors(verbose=not args.quiet)
        return
    export_pyg_graph(anchor_month=args.anchor_month, verbose=not args.quiet)


if __name__ == "__main__":
    main()
