"""
Betweenness Centrality (BC) — identify gatekeeper brokers in the supply network.

BC distance weighting:
  ``bc_distance = hop_penalty + 1 / log1p(tx_count)`` — high-traffic lanes are
  shorter paths.  Computed on entity-level graph collapsed from product MultiDiGraph.

Subset BC: sources = manufacturers/importers (or in-degree 0); targets = hospitals.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

from .build_network import (
    build_rolling_main_graph,
    collapse_to_digraph,
    network_summary,
)

BC_HIGH_RISK_PERCENTILE = 0.95  # top 5%

_SOURCE_TYPES = {"manufacturer", "importer"}
_SINK_TYPES = {"hospital"}


def _bc_sources_targets(G: nx.DiGraph) -> tuple[list, list]:
    sources = [
        n
        for n, d in G.nodes(data=True)
        if d.get("canonical_node_type", d.get("node_type")) in _SOURCE_TYPES
        or G.in_degree(n) == 0
    ]
    targets = [
        n
        for n, d in G.nodes(data=True)
        if d.get("canonical_node_type", d.get("node_type")) in _SINK_TYPES
    ]
    return sources, targets


def compute_betweenness_centrality(
    supply: pd.DataFrame,
    *,
    verbose: bool = True,
    normalized: bool = True,
) -> pd.DataFrame:
    """
    Compute betweenness centrality over the rolling-window main supply network.

    Uses ``betweenness_centrality_subset`` with hop-penalised inverse-frequency
    distance on the entity-level collapsed graph.
    """
    G_multi = build_rolling_main_graph(supply)
    G = collapse_to_digraph(G_multi)

    if verbose:
        stats = network_summary(G_multi)
        print(f"[BC] Network: {stats['nodes']} nodes, {stats['edges']} product edges")
        print(f"     Collapsed entity edges: {G.number_of_edges():,}")
        print(f"     Node types: {stats['node_types']}")
        print(f"     Density: {stats['density']}")
        print(
            "[BC] Computing subset betweenness centrality "
            "(manufacturer/importer → hospital; may take a moment)..."
        )

    sources, targets = _bc_sources_targets(G)
    if not sources or not targets:
        bc_raw = nx.betweenness_centrality(G, normalized=normalized, weight="bc_distance")
    else:
        bc_raw = nx.betweenness_centrality_subset(
            G,
            sources=sources,
            targets=targets,
            normalized=normalized,
            weight="bc_distance",
        )

    records = []
    for node, bc in bc_raw.items():
        attrs = G.nodes[node]
        node_type = attrs.get("canonical_node_type", attrs.get("node_type", "other"))
        records.append({
            "entity_id": node,
            "name": attrs.get("name", ""),
            "node_type": node_type,
            "bc_score": round(bc, 8),
            "in_degree": G.in_degree(node),
            "out_degree": G.out_degree(node),
        })

    result = pd.DataFrame(records).sort_values("bc_score", ascending=False)

    if len(result) == 0:
        return result

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
        "high_risk_count": int(bc_df["high_risk"].sum()) if len(bc_df) else 0,
        "high_risk_pct": round(float(bc_df["high_risk"].mean()), 4) if len(bc_df) else 0.0,
        "bc_max": float(bc_df["bc_score"].max()) if len(bc_df) else 0.0,
        "bc_mean": float(bc_df["bc_score"].mean()) if len(bc_df) else 0.0,
        "bc_p95": float(bc_df["bc_score"].quantile(0.95)) if len(bc_df) else 0.0,
        "by_node_type": (
            bc_df.groupby("node_type")["bc_score"]
            .agg(["mean", "max", "count"])
            .round(6)
            .to_dict("index")
            if len(bc_df)
            else {}
        ),
    }
