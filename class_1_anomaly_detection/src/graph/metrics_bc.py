"""
Betweenness Centrality (BC) — identify gatekeeper brokers in the supply network.

Definition (from methods memo):
  BC(v) = Σ_{s≠v≠t} σ_st(v) / σ_st
  where σ_st = total shortest paths from supplier s to hospital t,
        σ_st(v) = those paths passing through v.

Regulatory threshold: nodes in the top 5% of BC are flagged as high-risk
gatekeeper brokers ("통행세 취득원" — toll-booth extractors).

Key design choice (PM-confirmed):
  - Include zero-price B2B edges in BC computation (physical flow topology).
  - Normalise BC by node business type and network size to avoid flagging
    legitimate large-scale distributors as false positives.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

from .build_network import build_supply_network, network_summary

BC_HIGH_RISK_PERCENTILE = 0.95  # top 5%


def compute_betweenness_centrality(
    supply: pd.DataFrame,
    *,
    verbose: bool = True,
    normalized: bool = True,
) -> pd.DataFrame:
    """
    Compute betweenness centrality over the full supply network.

    Zero-price B2B edges are included (physical flow topology).
    Hospital-only edges are not filtered here — BC is a global metric.

    Parameters
    ----------
    supply:
        Top7 supply DataFrame.
    normalized:
        Divide raw BC by (n-1)(n-2) for comparability across differently-sized
        networks.

    Returns
    -------
    pd.DataFrame with columns:
      - entity_id: node identifier
      - name: company name
      - node_type: manufacturer / importer / distributor / hospital / unknown
      - bc_score: betweenness centrality value
      - high_risk: True if bc_score >= 95th percentile
      - in_degree: number of upstream suppliers
      - out_degree: number of downstream receivers
    """
    G = build_supply_network(supply, include_zero_price=True, hospital_only=False)

    if verbose:
        stats = network_summary(G)
        print(f"[BC] Network: {stats['nodes']} nodes, {stats['edges']} edges")
        print(f"     Node types: {stats['node_types']}")
        print(f"     Density: {stats['density']}")
        print("[BC] Computing betweenness centrality (may take a moment for large graphs)...")

    bc_raw = nx.betweenness_centrality(G, normalized=normalized, weight="weight")

    records = []
    for node, bc in bc_raw.items():
        attrs = G.nodes[node]
        records.append({
            "entity_id": node,
            "name": attrs.get("name", ""),
            "node_type": attrs.get("node_type", "unknown"),
            "bc_score": round(bc, 8),
            "in_degree": G.in_degree(node),
            "out_degree": G.out_degree(node),
        })

    result = pd.DataFrame(records).sort_values("bc_score", ascending=False)

    threshold = result["bc_score"].quantile(BC_HIGH_RISK_PERCENTILE)
    result["high_risk"] = result["bc_score"] >= threshold

    if verbose:
        high_risk_nodes = result[result["high_risk"]]
        print(f"[BC] High-risk nodes (top 5%): {len(high_risk_nodes)}/{len(result)}")
        print(f"[BC] BC threshold (p95): {threshold:.10f}")
        if len(high_risk_nodes) > 0:
            print(
                high_risk_nodes[["entity_id", "name", "node_type", "bc_score"]]
                .head(20)
                .to_string(index=False)
            )

    return result


def bc_summary(bc_df: pd.DataFrame) -> dict:
    return {
        "total_nodes": len(bc_df),
        "high_risk_count": int(bc_df["high_risk"].sum()),
        "high_risk_pct": round(float(bc_df["high_risk"].mean()), 4),
        "bc_max": float(bc_df["bc_score"].max()),
        "bc_mean": float(bc_df["bc_score"].mean()),
        "bc_p95": float(bc_df["bc_score"].quantile(0.95)),
        "by_node_type": (
            bc_df.groupby("node_type")["bc_score"]
            .agg(["mean", "max", "count"])
            .round(6)
            .to_dict("index")
        ),
    }
