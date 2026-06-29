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
  python -m class_1_anomaly_detection.src.experiments.export_pyg_graph
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

OUTPUT_DIR = _REPO_ROOT / "class_1_anomaly_detection" / "output"
PYG_DIR = OUTPUT_DIR / "pyg"

NODE_TYPE_VALUES = (
    "manufacturer",
    "importer",
    "distributor",
    "hospital",
    "other",
    "unknown",
)

CONTINUOUS_FEATURES = [
    "in_degree",
    "out_degree",
    "in_weight_log",
    "out_weight_log",
    "in_tx_log",
    "out_tx_log",
    "bc_score",
    "price_flag_rate",
    "price_median_z",
    "price_max_z",
    "timelag_median_log",
    "timelag_max_log",
]


def _load_csv(name: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path.relative_to(_REPO_ROOT)} — run run_graph_eda.py first."
        )
    return pd.read_csv(path)


def _log1p_nonneg(series: pd.Series) -> pd.Series:
    return np.log1p(series.fillna(0).clip(lower=0))


def _degree_features(edges: pd.DataFrame, node_ids: list[str]) -> pd.DataFrame:
    """Aggregate directed degree and weight sums per entity."""
    idx = {eid: i for i, eid in enumerate(node_ids)}
    n = len(node_ids)

    in_deg = np.zeros(n, dtype=np.float64)
    out_deg = np.zeros(n, dtype=np.float64)
    in_weight = np.zeros(n, dtype=np.float64)
    out_weight = np.zeros(n, dtype=np.float64)
    in_tx = np.zeros(n, dtype=np.float64)
    out_tx = np.zeros(n, dtype=np.float64)

    for row in edges.itertuples(index=False):
        src = str(row.src)
        dst = str(row.dst)
        weight = float(row.weight) if pd.notna(row.weight) else 0.0
        tx_count = float(row.tx_count) if pd.notna(row.tx_count) else 0.0

        if src in idx:
            si = idx[src]
            out_deg[si] += 1
            out_weight[si] += max(weight, 0.0)
            out_tx[si] += max(tx_count, 0.0)
        if dst in idx:
            di = idx[dst]
            in_deg[di] += 1
            in_weight[di] += max(weight, 0.0)
            in_tx[di] += max(tx_count, 0.0)

    return pd.DataFrame(
        {
            "entity_id": node_ids,
            "in_degree": in_deg,
            "out_degree": out_deg,
            "in_weight_log": _log1p_nonneg(pd.Series(in_weight)),
            "out_weight_log": _log1p_nonneg(pd.Series(out_weight)),
            "in_tx_log": _log1p_nonneg(pd.Series(in_tx)),
            "out_tx_log": _log1p_nonneg(pd.Series(out_tx)),
        }
    )


def _one_hot_node_types(node_types: pd.Series) -> pd.DataFrame:
    normalized = node_types.fillna("unknown").astype(str).str.strip().str.lower()
    normalized = normalized.where(normalized.isin(NODE_TYPE_VALUES), "unknown")
    return pd.get_dummies(normalized, prefix="type")
    # columns: type_<value>


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
    features = features.merge(
        lag_cols[["entity_id", "median_lag_days", "max_lag_days"]],
        on="entity_id",
        how="left",
    )
    features["timelag_median_log"] = _log1p_nonneg(features["median_lag_days"])
    features["timelag_max_log"] = _log1p_nonneg(features["max_lag_days"])
    features.drop(columns=["median_lag_days", "max_lag_days"], inplace=True)

    type_dummies = _one_hot_node_types(features["node_type"])
    type_dummies.index = features.index
    features = pd.concat([features.drop(columns=["node_type"]), type_dummies], axis=1)

    feature_names = CONTINUOUS_FEATURES + sorted(
        c for c in features.columns if c.startswith("type_")
    )
    return features, feature_names


def build_edge_tensors(
    edges: pd.DataFrame,
    entity_to_idx: dict[str, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Build directed edge_index [2, E] and edge_attr [E, 2]."""
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
        src_idx.append(entity_to_idx[src])
        dst_idx.append(entity_to_idx[dst])
        attrs.append([float(np.log1p(max(weight, 0.0))), float(np.log1p(max(tx_count, 0.0)))])

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


def export_pyg_graph(*, verbose: bool = True) -> Path:
    """Load CSV artifacts, build tensors, save PyG-ready outputs."""
    nodes = _load_csv("network_nodes")
    edges = _load_csv("network_edges")
    bc = _load_csv("bc_per_entity")
    price = _load_csv("price_zscore_per_entity")
    timelag = _load_csv("timelag_per_entity")

    features, feature_names = build_node_features(nodes, edges, bc, price, timelag)
    entity_ids = features["entity_id"].astype(str).tolist()
    entity_to_idx = {eid: i for i, eid in enumerate(entity_ids)}

    edge_index, edge_attr = build_edge_tensors(edges, entity_to_idx)

    x_raw = features[feature_names].to_numpy(dtype=np.float32)
    scaler = StandardScaler()
    x = scaler.fit_transform(x_raw).astype(np.float32)

    sanity = build_sanity_report(features, edge_index, feature_names, x)

    PYG_DIR.mkdir(parents=True, exist_ok=True)

    index_map = features[["entity_id"]].copy()
    index_map.insert(0, "tensor_index", range(len(index_map)))
    index_map.to_csv(PYG_DIR / "node_index_map.csv", index=False, encoding="utf-8-sig")

    with open(PYG_DIR / "feature_columns.json", "w", encoding="utf-8") as f:
        json.dump(feature_names, f, indent=2)

    np.savez(
        PYG_DIR / "graph_tensors.npz",
        x=x,
        edge_index=edge_index,
        edge_attr=edge_attr,
    )

    with open(PYG_DIR / "pyg_sanity_report.json", "w", encoding="utf-8") as f:
        json.dump(sanity, f, indent=2, ensure_ascii=False)

    pt_path = PYG_DIR / "pyg_data.pt"
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
        print(f"  Output dir         : {PYG_DIR.relative_to(_REPO_ROOT)}")
        if sanity.get("pyg_data_pt"):
            print(f"  PyG artifact       : {sanity['pyg_data_pt']}")
        else:
            print(f"  Install hint       : {sanity.get('pyg_install_hint')}")
        print("=" * 70)

    return PYG_DIR


if __name__ == "__main__":
    export_pyg_graph(verbose=True)
