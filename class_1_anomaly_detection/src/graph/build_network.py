"""
Directed supply-chain network builder for Class 1 anomaly detection.

Graph semantics (spec §2 착수보고서 — Node list):
  - Nodes: supply-chain entities identified by 업체일련번호 (system-generated
    company serial, always a clean int) as the primary key.  Falls back to
    사업자등록번호, then hospital code, then company name.  Using the
    system serial eliminates the .0-suffix fragmentation that caused 528 WCCs.
  - Directed edges: supplier → receiver per transaction row.
  - Edge weight: 공급금액 (supply amount); zero-price B2B edges are retained
    for topology (PDI, BC) but excluded from amount-weighted metrics (HHI).
  - Node type attribute: derived from 업종 / 공급받은자업종 columns to
    classify manufacturer, importer, distributor, medical institution.
  - Discard transactions (공급구분 = 폐기) are excluded — no valid receiver.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

from ..ingest.keys import (
    DISCARD_SUPPLY_CLASS,
    HOSPITAL_SUPPLY_TYPE,
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
    COL_SUPPLY_TYPE,
    COL_AMOUNT,
    COL_UNIT_PRICE,
)

_COL_DATE = "공급일자"
_COL_UDI = "UDI-DI"


def build_supply_network(
    supply: pd.DataFrame,
    *,
    include_zero_price: bool = True,
    hospital_only: bool = False,
) -> nx.DiGraph:
    """
    Build a directed weighted supply-chain graph from the top7 supply DataFrame.

    Parameters
    ----------
    supply:
        Output of :func:`loader.load_supply` (price-capped, schema-validated).
    include_zero_price:
        Keep zero-price and null-price edges (required for correct PDI and BC).
        Set False only when building amount-weighted graphs (HHI).
    hospital_only:
        Filter to ``공급형태 = 의료기관에 공급`` before building the graph.
        Use for HHI and pricing anomaly metrics.

    Returns
    -------
    nx.DiGraph
        Each edge carries attributes:
          - weight (float): sum of 공급금액 across all transactions on that edge
          - tx_count (int): number of transaction rows on that edge
          - has_zero_price (bool): any zero/null price rows in edge batch
    """
    df = supply.copy()

    # Exclude discard transactions — no valid receiver
    if COL_SUPPLY_CLASS in df.columns:
        df = df[df[COL_SUPPLY_CLASS] != DISCARD_SUPPLY_CLASS]

    if hospital_only and COL_SUPPLY_TYPE in df.columns:
        df = df[df[COL_SUPPLY_TYPE] == HOSPITAL_SUPPLY_TYPE]

    if not include_zero_price and COL_AMOUNT in df.columns:
        df = df[df[COL_AMOUNT].notna() & (df[COL_AMOUNT] > 0)]

    G = nx.DiGraph()

    for _, row in df.iterrows():
        src_id = normalize_supply_entity_id(
            row.get(COL_SUPPLIER_SERIAL),
            row.get(COL_SUPPLIER_REG),
            row.get(COL_SUPPLIER_NAME),
        )
        dst_id = normalize_receiver_entity_id(
            row.get(COL_RECEIVER_SERIAL),
            row.get(COL_RECEIVER_REG),
            row.get(COL_RECEIVER_NAME),
            hospital_code=row.get(COL_HOSPITAL_CODE),
        )

        if src_id == "unknown" or dst_id == "unknown":
            continue

        if src_id not in G:
            G.add_node(
                src_id,
                name=str(row.get(COL_SUPPLIER_NAME, "")).strip(),
                node_type=classify_node_type(row.get(COL_SUPPLIER_TYPE)),
            )
        if dst_id not in G:
            G.add_node(
                dst_id,
                name=str(row.get(COL_RECEIVER_NAME, "")).strip(),
                node_type=classify_node_type(
                    row.get(COL_RECEIVER_TYPE),
                    hospital_code=row.get(COL_HOSPITAL_CODE),
                ),
            )

        amount = row.get(COL_AMOUNT)
        amount_val = float(amount) if pd.notna(amount) else 0.0
        price_val = row.get(COL_UNIT_PRICE)
        is_zero = not (pd.notna(price_val) and float(price_val) > 0)

        if G.has_edge(src_id, dst_id):
            G[src_id][dst_id]["weight"] += amount_val
            G[src_id][dst_id]["tx_count"] += 1
            G[src_id][dst_id]["has_zero_price"] |= is_zero
        else:
            G.add_edge(
                src_id,
                dst_id,
                weight=amount_val,
                tx_count=1,
                has_zero_price=is_zero,
            )

    return G


def network_summary(G: nx.DiGraph) -> dict:
    """Return basic network statistics."""
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "density": round(nx.density(G), 6),
        "weakly_connected_components": nx.number_weakly_connected_components(G),
        "node_types": _count_node_types(G),
    }


def _count_node_types(G: nx.DiGraph) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, attrs in G.nodes(data=True):
        t = attrs.get("node_type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts
