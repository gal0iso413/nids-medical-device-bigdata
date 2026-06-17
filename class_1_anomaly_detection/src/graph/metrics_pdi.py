"""
Path Depth Index (PDI) — detect indirect supply and multi-stage detours.

Definition (spec §3 착수보고서):
  PDI_udi = max path length from any source node (in-degree=0 or type=manufacturer/importer)
            to any sink node (type=hospital) through edges carrying that UDI-DI.

Regulatory threshold: PDI >= 3 triggers a high-risk indirect-supply flag.
Spec note (Phase 1): differential thresholds by device class are intended but the exact
per-class values are a PM decision.  Phase 1 enriches the output with ``device_class``
(from master join) so the PM can set class-specific gates later without recomputation.
"""
from __future__ import annotations

import pandas as pd
import networkx as nx

from ..ingest.keys import (
    DISCARD_SUPPLY_CLASS,
    classify_node_type,
    normalize_supply_entity_id,
    normalize_receiver_entity_id,
    COL_SUPPLIER_SERIAL,
    COL_SUPPLIER_REG,
    COL_SUPPLIER_NAME,
    COL_SUPPLIER_TYPE,
    COL_RECEIVER_SERIAL,
    COL_RECEIVER_REG,
    COL_RECEIVER_NAME,
    COL_RECEIVER_TYPE,
    COL_HOSPITAL_CODE,
    COL_SUPPLY_CLASS,
)

_COL_UDI = "UDI-DI"
_COL_DATE = "공급일자"

PDI_HIGH_RISK_THRESHOLD = 3

_SOURCE_TYPES = {"manufacturer", "importer"}
_SINK_TYPES = {"hospital"}


def _build_udi_graph(df_udi: pd.DataFrame) -> nx.DiGraph:
    """Build a directed graph for a single UDI-DI."""
    G = nx.DiGraph()
    for _, row in df_udi.iterrows():
        src = normalize_supply_entity_id(
            row.get(COL_SUPPLIER_SERIAL),
            row.get(COL_SUPPLIER_REG),
            row.get(COL_SUPPLIER_NAME),
        )
        dst = normalize_receiver_entity_id(
            row.get(COL_RECEIVER_SERIAL),
            row.get(COL_RECEIVER_REG),
            row.get(COL_RECEIVER_NAME),
            hospital_code=row.get(COL_HOSPITAL_CODE),
        )
        if src == "unknown" or dst == "unknown" or src == dst:
            continue
        src_type = classify_node_type(row.get(COL_SUPPLIER_TYPE))
        dst_type = classify_node_type(
            row.get(COL_RECEIVER_TYPE),
            hospital_code=row.get(COL_HOSPITAL_CODE),
        )
        if src not in G:
            G.add_node(src, node_type=src_type)
        if dst not in G:
            G.add_node(dst, node_type=dst_type)
        if not G.has_edge(src, dst):
            G.add_edge(src, dst)
    return G


def _max_source_to_sink_path(G: nx.DiGraph) -> int:
    """
    Return the length of the longest simple path from any source to any sink.
    Source: in-degree=0 OR node_type in {manufacturer, importer}.
    Sink: node_type = hospital.
    Returns 0 if no valid source-to-sink path exists.
    """
    sources = [
        n for n, d in G.nodes(data=True)
        if G.in_degree(n) == 0 or d.get("node_type") in _SOURCE_TYPES
    ]
    sinks = [
        n for n, d in G.nodes(data=True)
        if d.get("node_type") in _SINK_TYPES
    ]
    if not sources or not sinks:
        return 0

    max_len = 0
    for src in sources:
        for snk in sinks:
            if src == snk:
                continue
            try:
                # Use simple paths to avoid cycles; take the longest one found
                for path in nx.all_simple_paths(G, src, snk, cutoff=10):
                    max_len = max(max_len, len(path) - 1)
            except nx.NetworkXNoPath:
                continue
            except nx.NodeNotFound:
                continue
    return max_len


def compute_pdi(
    supply: pd.DataFrame,
    *,
    master: pd.DataFrame | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Compute Path Depth Index for each unique UDI-DI in the supply DataFrame.

    Parameters
    ----------
    supply:
        Top7 supply DataFrame (loaded + price-capped).
    master:
        Optional top7 master DataFrame.  When provided the output is enriched
        with ``device_class`` (등급) per UDI-DI.  The spec (Phase 1) requires
        differential PDI thresholds by device class; the exact class-specific
        values are a PM decision — this column enables that gate without
        recomputation.

    Returns
    -------
    pd.DataFrame with columns:
      - udi_di: UDI-DI value
      - pdi: max hop count from source to hospital
      - high_risk: True if pdi >= PDI_HIGH_RISK_THRESHOLD
      - device_class: device grade from master (if master supplied, else NaN)
      - tx_count: number of supply rows for this UDI-DI
      - unique_suppliers: supplier entity count
      - unique_receivers: receiver entity count
    """
    if COL_SUPPLY_CLASS in supply.columns:
        df = supply[supply[COL_SUPPLY_CLASS] != DISCARD_SUPPLY_CLASS].copy()
    else:
        df = supply.copy()

    if _COL_UDI not in df.columns:
        raise KeyError(f"Column '{_COL_UDI}' not found in supply DataFrame.")

    # Build UDI-DI → device class lookup from master if provided
    udi_class: dict[str, str] = {}
    if master is not None and "UDI-DI" in master.columns and "등급" in master.columns:
        for _, mrow in master[["UDI-DI", "등급"]].drop_duplicates().iterrows():
            udi_val = str(mrow["UDI-DI"]).strip()
            grade = str(mrow["등급"]).strip() if pd.notna(mrow["등급"]) else ""
            if udi_val and grade:
                udi_class[udi_val] = grade

    records = []
    udis = df[_COL_UDI].dropna().unique()
    if verbose:
        print(f"[PDI] Computing for {len(udis)} unique UDI-DI values...")

    for udi in udis:
        df_udi = df[df[_COL_UDI] == udi]
        G = _build_udi_graph(df_udi)
        pdi = _max_source_to_sink_path(G)

        sup_ids = set()
        rec_ids = set()
        for _, row in df_udi.iterrows():
            sup_ids.add(
                normalize_supply_entity_id(
                    row.get(COL_SUPPLIER_SERIAL),
                    row.get(COL_SUPPLIER_REG),
                    row.get(COL_SUPPLIER_NAME),
                )
            )
            rec_ids.add(
                normalize_receiver_entity_id(
                    row.get(COL_RECEIVER_SERIAL),
                    row.get(COL_RECEIVER_REG),
                    row.get(COL_RECEIVER_NAME),
                    hospital_code=row.get(COL_HOSPITAL_CODE),
                )
            )
        sup_ids.discard("unknown")
        rec_ids.discard("unknown")

        records.append({
            "udi_di": udi,
            "pdi": pdi,
            "high_risk": pdi >= PDI_HIGH_RISK_THRESHOLD,
            "device_class": udi_class.get(str(udi).strip(), float("nan")),
            "tx_count": len(df_udi),
            "unique_suppliers": len(sup_ids),
            "unique_receivers": len(rec_ids),
        })

    result = pd.DataFrame(records).sort_values("pdi", ascending=False)

    if verbose:
        high_risk_count = result["high_risk"].sum()
        print(f"[PDI] High-risk UDIs (PDI≥{PDI_HIGH_RISK_THRESHOLD}): "
              f"{high_risk_count}/{len(result)} ({high_risk_count/len(result):.1%})")
        print(result[["udi_di", "pdi", "high_risk", "device_class", "tx_count"]].to_string(index=False))

    return result


def pdi_summary(pdi_df: pd.DataFrame) -> dict:
    return {
        "total_udis": len(pdi_df),
        "high_risk_count": int(pdi_df["high_risk"].sum()),
        "high_risk_pct": round(float(pdi_df["high_risk"].mean()), 4),
        "pdi_max": int(pdi_df["pdi"].max()),
        "pdi_mean": round(float(pdi_df["pdi"].mean()), 2),
        "pdi_median": int(pdi_df["pdi"].median()),
        "distribution": pdi_df["pdi"].value_counts().sort_index().to_dict(),
    }
