"""
Directed supply-chain network builder for Class 1 anomaly detection.

Graph semantics (spec §2 착수보고서 — Node list):
  - Nodes: supply-chain entities identified by 업체일련번호 (system-generated
    company serial) as the primary key, with multi-role tracking.
  - Directed edges: supplier → receiver per product composite
    (item_serial, model_serial, udi_serial) — 출고 only.
  - Main graph: 3-month rolling window (no month in edge key) for PDI/BC.
  - Monthly GNN snapshots: same edge skeleton, per-month edge_attr tensors.
"""
from __future__ import annotations

import math
from typing import Any

import networkx as nx
import pandas as pd

from ..ingest.keys import (
    BARCODE_PRICE_THRESHOLD,
    ROLLING_WINDOW_MONTHS,
    VALID_SUPPLY_CLASSES,
    HOSPITAL_SUPPLY_TYPE,
    classify_node_type,
    normalize_supply_entity_id,
    normalize_receiver_entity_id,
    strip_float_suffix,
    yn_to_bool,
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
    COL_SUPPLY_QTY,
    COL_ITEM_SERIAL,
    COL_MODEL_SERIAL,
    COL_UDI_SERIAL,
    COL_BASE_MONTH,
    COL_LOCATION_SUPPLIER,
    COL_LOCATION_RECEIVER,
    COL_DEVICE_CLASS,
    COL_TRACEABLE,
    COL_REIMBURSABLE,
)

HOP_PENALTY: float = 1.0

_TYPE_PRIORITY: dict[str, int] = {
    "hospital": 0,
    "manufacturer": 1,
    "importer": 2,
    "distributor": 3,
    "other": 4,
}


def _resolve_node_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``_src_id`` and ``_dst_id`` columns for every supply row."""
    out = df.copy()
    out["_src_id"] = out.apply(
        lambda r: normalize_supply_entity_id(
            r.get(COL_SUPPLIER_SERIAL),
            r.get(COL_SUPPLIER_REG),
            r.get(COL_SUPPLIER_NAME),
        ),
        axis=1,
    )
    out["_dst_id"] = out.apply(
        lambda r: normalize_receiver_entity_id(
            r.get(COL_RECEIVER_SERIAL),
            r.get(COL_RECEIVER_REG),
            r.get(COL_RECEIVER_NAME),
            hospital_code=r.get(COL_HOSPITAL_CODE),
        ),
        axis=1,
    )
    return out


def _serial_str(series: pd.Series) -> pd.Series:
    """Normalise integer-like serial columns to stable string keys."""
    if series is None or series.empty:
        return pd.Series(dtype=str)
    if pd.api.types.is_numeric_dtype(series):
        return strip_float_suffix(series).astype("Int64").astype(str)
    return series.astype(str).str.strip()


def _product_key_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``_item_serial``, ``_model_serial``, ``_udi_serial``, ``_product_key``."""
    out = df.copy()
    out["_item_serial"] = (
        _serial_str(out[COL_ITEM_SERIAL]) if COL_ITEM_SERIAL in out.columns else "0"
    )
    out["_model_serial"] = (
        _serial_str(out[COL_MODEL_SERIAL]) if COL_MODEL_SERIAL in out.columns else "0"
    )
    out["_udi_serial"] = (
        _serial_str(out[COL_UDI_SERIAL]) if COL_UDI_SERIAL in out.columns else "0"
    )
    out["_product_key"] = (
        out["_item_serial"] + "_" + out["_model_serial"] + "_" + out["_udi_serial"]
    )
    return out


def _clean_amount_with_fallback(df: pd.DataFrame) -> pd.Series:
    """
    Return cleaned transaction amounts.

    Barcode-class 공급금액 values fall back to 공급단가 × 공급수량 when valid.
    """
    if COL_AMOUNT not in df.columns:
        return pd.Series(0.0, index=df.index)

    amount = pd.to_numeric(df[COL_AMOUNT], errors="coerce").fillna(0.0)
    unit_price = (
        pd.to_numeric(df[COL_UNIT_PRICE], errors="coerce").fillna(0.0)
        if COL_UNIT_PRICE in df.columns
        else pd.Series(0.0, index=df.index)
    )
    qty = (
        pd.to_numeric(df[COL_SUPPLY_QTY], errors="coerce").fillna(0.0)
        if COL_SUPPLY_QTY in df.columns
        else pd.Series(0.0, index=df.index)
    )

    barcode_mask = amount >= BARCODE_PRICE_THRESHOLD
    fallback = unit_price * qty
    valid_fallback = (
        (unit_price > 0)
        & (unit_price < BARCODE_PRICE_THRESHOLD)
        & (qty > 0)
    )
    fallback = fallback.where(valid_fallback, 0.0)

    cleaned = amount.where(~barcode_mask, fallback)
    cleaned = cleaned.where(cleaned < BARCODE_PRICE_THRESHOLD, 0.0)
    return cleaned


def _device_class_int(series: pd.Series) -> pd.Series:
    """Extract numeric device grade (1–4) from 등급 column."""
    if series is None or series.empty:
        return pd.Series(dtype=int)
    as_num = pd.to_numeric(series, errors="coerce")
    if as_num.notna().any():
        return as_num.fillna(0).astype(int)
    extracted = series.astype(str).str.extract(r"(\d+)", expand=False)
    return pd.to_numeric(extracted, errors="coerce").fillna(0).astype(int)


def _month_set_agg(series: pd.Series) -> frozenset[str]:
    """Collect distinct non-null months from a group."""
    vals = series.dropna().astype(str).str.strip()
    return frozenset(v for v in vals.unique() if v and v.lower() not in {"nan", "none"})


def _bc_distance(tx_count: int) -> float:
    return HOP_PENALTY + 1.0 / math.log1p(max(tx_count, 1))


def _merge_node_type(a: str, b: str) -> str:
    pa = _TYPE_PRIORITY.get(a, 99)
    pb = _TYPE_PRIORITY.get(b, 99)
    return a if pa <= pb else b


def _build_edge_table_multikey(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate rows into one record per (src, dst, product composite)."""
    work = df.copy()
    if COL_UNIT_PRICE in work.columns:
        work["_is_zero_price"] = ~(
            work[COL_UNIT_PRICE].notna()
            & (pd.to_numeric(work[COL_UNIT_PRICE], errors="coerce") > 0)
        )
    else:
        work["_is_zero_price"] = True
    work["_amount_clean"] = _clean_amount_with_fallback(work)
    work["_device_class_int"] = (
        _device_class_int(work[COL_DEVICE_CLASS])
        if COL_DEVICE_CLASS in work.columns
        else 0
    )
    work["_traceable"] = (
        work[COL_TRACEABLE].map(yn_to_bool)
        if COL_TRACEABLE in work.columns
        else False
    )
    work["_reimbursable"] = (
        work[COL_REIMBURSABLE].map(yn_to_bool)
        if COL_REIMBURSABLE in work.columns
        else False
    )
    if COL_BASE_MONTH in work.columns:
        work["_month_str"] = work[COL_BASE_MONTH].astype(str).str.strip()
    else:
        work["_month_str"] = ""

    group_cols = ["_src_id", "_dst_id", "_item_serial", "_model_serial", "_udi_serial", "_product_key"]
    grouped = work.groupby(group_cols, sort=False)

    edge_table = grouped.agg(
        weight=("_amount_clean", "sum"),
        tx_count=("_amount_clean", "count"),
        has_zero_price=("_is_zero_price", "any"),
        has_traceable=("_traceable", "any"),
        has_reimbursable=("_reimbursable", "any"),
        max_device_class=("_device_class_int", "max"),
        first_month=("_month_str", "min"),
        last_month=("_month_str", "max"),
    ).reset_index()

    month_col = COL_BASE_MONTH if COL_BASE_MONTH in work.columns else "_month_str"
    month_sets = (
        work.groupby(group_cols, sort=False)[month_col]
        .apply(_month_set_agg)
        .reset_index(name="month_set")
    )
    edge_table = edge_table.rename(columns={"_src_id": "src", "_dst_id": "dst"})
    month_sets = month_sets.rename(columns={"_src_id": "src", "_dst_id": "dst"})
    merge_cols = ["src", "dst", "_item_serial", "_model_serial", "_udi_serial", "_product_key"]
    edge_table = edge_table.merge(month_sets, on=merge_cols, how="left")
    edge_table["month_set"] = edge_table["month_set"].apply(
        lambda x: x if isinstance(x, frozenset) else frozenset()
    )
    edge_table["active_month_count"] = edge_table["month_set"].map(len)

    edge_table["tx_count"] = edge_table["tx_count"].astype(int)
    edge_table["max_device_class"] = edge_table["max_device_class"].astype(int)
    edge_table["unique_udi_count"] = 1  # one UDI serial per product edge
    return edge_table


def _build_node_table_multirole(df: pd.DataFrame) -> pd.DataFrame:
    """Extract one row per entity with multi-role and canonical type."""
    records: dict[str, dict[str, Any]] = {}

    def _upsert(
        entity_id: str,
        *,
        name: str,
        node_type: str,
        location: str,
        ever_supplier: bool = False,
        ever_receiver: bool = False,
    ) -> None:
        if entity_id not in records:
            records[entity_id] = {
                "entity_id": entity_id,
                "name": name,
                "canonical_node_type": node_type,
                "location_counts": {},
                "ever_supplier": False,
                "ever_receiver": False,
            }
        rec = records[entity_id]
        if name and not rec["name"]:
            rec["name"] = name
        rec["canonical_node_type"] = _merge_node_type(
            rec["canonical_node_type"], node_type
        )
        loc = str(location).strip() if location is not None else ""
        if loc and loc.lower() not in {"nan", "none"}:
            rec["location_counts"][loc] = rec["location_counts"].get(loc, 0) + 1
        rec["ever_supplier"] = rec["ever_supplier"] or ever_supplier
        rec["ever_receiver"] = rec["ever_receiver"] or ever_receiver

    work = df.rename(columns={"_src_id": "src_id", "_dst_id": "dst_id"})
    for row in work.itertuples(index=False):
        src_type = classify_node_type(getattr(row, COL_SUPPLIER_TYPE, None))
        dst_type = classify_node_type(
            getattr(row, COL_RECEIVER_TYPE, None),
            hospital_code=getattr(row, COL_HOSPITAL_CODE, None),
        )
        _upsert(
            row.src_id,
            name=str(getattr(row, COL_SUPPLIER_NAME, "") or "").strip(),
            node_type=src_type,
            location=getattr(row, COL_LOCATION_SUPPLIER, ""),
            ever_supplier=True,
        )
        _upsert(
            row.dst_id,
            name=str(getattr(row, COL_RECEIVER_NAME, "") or "").strip(),
            node_type=dst_type,
            location=getattr(row, COL_LOCATION_RECEIVER, ""),
            ever_receiver=True,
        )

    rows = []
    for rec in records.values():
        loc_counts = rec.pop("location_counts")
        location = max(loc_counts, key=loc_counts.get) if loc_counts else ""
        rows.append({**rec, "location": location})

    return pd.DataFrame(rows)


def _graph_from_tables(
    node_table: pd.DataFrame,
    edge_table: pd.DataFrame,
) -> nx.MultiDiGraph:
    """Assemble a NetworkX MultiDiGraph from pre-aggregated node/edge tables."""
    G = nx.MultiDiGraph()
    for row in node_table.itertuples(index=False):
        G.add_node(
            row.entity_id,
            name=row.name,
            canonical_node_type=row.canonical_node_type,
            node_type=row.canonical_node_type,  # backward-compat alias
            location=row.location,
            ever_supplier=bool(row.ever_supplier),
            ever_receiver=bool(row.ever_receiver),
        )
    for rec in edge_table.to_dict("records"):
        src, dst = rec["src"], rec["dst"]
        if src not in G or dst not in G:
            continue
        tx_count = max(int(rec["tx_count"]), 1)
        product_key = str(rec["_product_key"])
        G.add_edge(
            src,
            dst,
            key=product_key,
            product_key=product_key,
            item_serial=str(rec["_item_serial"]),
            model_serial=str(rec["_model_serial"]),
            udi_serial=str(rec["_udi_serial"]),
            weight=float(rec["weight"]),
            tx_count=tx_count,
            has_zero_price=bool(rec["has_zero_price"]),
            unique_udi_count=int(rec["unique_udi_count"]),
            has_traceable=bool(rec["has_traceable"]),
            has_reimbursable=bool(rec["has_reimbursable"]),
            max_device_class=int(rec["max_device_class"]),
            first_month=str(rec.get("first_month") or ""),
            last_month=str(rec.get("last_month") or ""),
            active_month_count=int(rec.get("active_month_count") or 0),
            month_set=rec.get("month_set", frozenset()),
            bc_distance=_bc_distance(tx_count),
        )
    return G


def collapse_to_digraph(G: nx.MultiDiGraph) -> nx.DiGraph:
    """
    Collapse parallel product edges into entity-level (src, dst) pairs for BC.

    Sums ``tx_count`` and ``weight``; recomputes ``bc_distance`` from total traffic.
    """
    H = nx.DiGraph()
    for node, attrs in G.nodes(data=True):
        H.add_node(node, **attrs)

    pair_data: dict[tuple[str, str], dict[str, Any]] = {}
    for u, v, _key, data in G.edges(keys=True, data=True):
        pair = (u, v)
        if pair not in pair_data:
            pair_data[pair] = {
                "weight": 0.0,
                "tx_count": 0,
                "has_zero_price": False,
                "has_traceable": False,
                "has_reimbursable": False,
                "max_device_class": 0,
            }
        rec = pair_data[pair]
        rec["weight"] += float(data.get("weight", 0.0))
        rec["tx_count"] += int(data.get("tx_count", 0))
        rec["has_zero_price"] = rec["has_zero_price"] or bool(data.get("has_zero_price"))
        rec["has_traceable"] = rec["has_traceable"] or bool(data.get("has_traceable"))
        rec["has_reimbursable"] = rec["has_reimbursable"] or bool(
            data.get("has_reimbursable")
        )
        rec["max_device_class"] = max(
            rec["max_device_class"], int(data.get("max_device_class", 0))
        )

    for (u, v), rec in pair_data.items():
        tx_count = max(rec["tx_count"], 1)
        H.add_edge(
            u,
            v,
            weight=rec["weight"],
            tx_count=tx_count,
            has_zero_price=rec["has_zero_price"],
            has_traceable=rec["has_traceable"],
            has_reimbursable=rec["has_reimbursable"],
            max_device_class=rec["max_device_class"],
            bc_distance=_bc_distance(tx_count),
        )
    return H


def build_product_network(
    supply: pd.DataFrame,
    *,
    supply_classes: frozenset[str] | None = None,
    hospital_only: bool = False,
    month: str | None = None,
) -> nx.MultiDiGraph:
    """
    Build a directed product-level supply-chain graph from the top7 supply DataFrame.

    Edge key: ``(src, dst, item_serial, model_serial, udi_serial)`` — no month.

    Parameters
    ----------
    supply:
        Output of :func:`loader.load_supply`.
    supply_classes:
        Whitelist of ``공급구분`` values.  Defaults to ``VALID_SUPPLY_CLASSES`` (출고).
    hospital_only:
        Filter to ``공급형태 = 의료기관에 공급`` before building the graph.
    month:
        If given (e.g. ``"202601"``), filter to that ``공급내역기준연월``.

    Returns
    -------
    nx.MultiDiGraph
        Parallel edges per product composite; each carries global aggregates and
        ``bc_distance = hop_penalty + 1 / log1p(tx_count)``.
    """
    sc = supply_classes if supply_classes is not None else VALID_SUPPLY_CLASSES
    df = supply.copy()

    if COL_SUPPLY_CLASS in df.columns:
        df = df[df[COL_SUPPLY_CLASS].isin(sc)]

    if hospital_only and COL_SUPPLY_TYPE in df.columns:
        df = df[df[COL_SUPPLY_TYPE] == HOSPITAL_SUPPLY_TYPE]

    if month is not None and COL_BASE_MONTH in df.columns:
        df = df[df[COL_BASE_MONTH].astype(str).str.strip() == str(month)]

    if df.empty:
        return nx.MultiDiGraph()

    df = _resolve_node_ids(df)
    df = _product_key_cols(df)
    df = df[(df["_src_id"] != "unknown") & (df["_dst_id"] != "unknown")]
    df = df[df["_src_id"] != df["_dst_id"]]

    if df.empty:
        return nx.MultiDiGraph()

    node_table = _build_node_table_multirole(df)
    edge_table = _build_edge_table_multikey(df)
    return _graph_from_tables(node_table, edge_table)


def build_month_edge_aggregates(supply: pd.DataFrame, month: str) -> pd.DataFrame:
    """Aggregate product-level edges for a single ``공급내역기준연월``."""
    df = supply.copy()
    if COL_SUPPLY_CLASS in df.columns:
        df = df[df[COL_SUPPLY_CLASS].isin(VALID_SUPPLY_CLASSES)]
    if COL_BASE_MONTH in df.columns:
        df = df[df[COL_BASE_MONTH].astype(str).str.strip() == str(month)]
    if df.empty:
        return pd.DataFrame()

    df = _resolve_node_ids(df)
    df = _product_key_cols(df)
    df = df[(df["_src_id"] != "unknown") & (df["_dst_id"] != "unknown")]
    df = df[df["_src_id"] != df["_dst_id"]]
    if df.empty:
        return pd.DataFrame()
    return _build_edge_table_multikey(df)


def build_rolling_main_graph(
    supply: pd.DataFrame,
    *,
    anchor_month: str | None = None,
    window: int = ROLLING_WINDOW_MONTHS,
    supply_classes: frozenset[str] | None = None,
    hospital_only: bool = False,
) -> nx.MultiDiGraph:
    """
    Build the main tracking graph over a rolling month window (default 3 months).

    Used for PDI, BC, and the fixed GNN edge skeleton.  Edge keys exclude month;
    temporal detail is exported separately as per-month edge_attr tensors.
    """
    df, _ = select_rolling_window_supply(
        supply,
        anchor_month=anchor_month,
        window=window,
    )
    return build_product_network(
        df,
        supply_classes=supply_classes,
        hospital_only=hospital_only,
    )


def select_rolling_window_supply(
    supply: pd.DataFrame,
    *,
    anchor_month: str | None = None,
    window: int = ROLLING_WINDOW_MONTHS,
) -> tuple[pd.DataFrame, list[str]]:
    """Return supply rows and selected month list for a rolling month window."""
    if COL_BASE_MONTH not in supply.columns:
        return supply.copy(), []

    months = sorted(
        supply[COL_BASE_MONTH].dropna().astype(str).str.strip().unique()
    )
    if not months:
        return supply.copy(), []

    anchor = anchor_month if anchor_month is not None else months[-1]
    if anchor not in months:
        anchor = months[-1]
    anchor_idx = months.index(anchor)
    start_idx = max(0, anchor_idx - max(int(window), 1) + 1)
    selected = months[start_idx : anchor_idx + 1]
    df = supply[
        supply[COL_BASE_MONTH].astype(str).str.strip().isin(set(selected))
    ].copy()
    return df, selected


# Backward-compatible alias
build_supply_network = build_product_network


def build_monthly_network_stats(supply: pd.DataFrame) -> pd.DataFrame:
    """Build one network per ``공급내역기준연월`` and return summary statistics."""
    if COL_BASE_MONTH not in supply.columns:
        return pd.DataFrame()

    months = sorted(supply[COL_BASE_MONTH].dropna().astype(str).str.strip().unique())
    records: list[dict] = []
    for m in months:
        G = build_product_network(supply, month=m)
        stats = network_summary(G)
        stats.pop("node_types", None)
        stats["month"] = m
        records.append(stats)
    return pd.DataFrame(records).sort_values("month")


def network_summary(G: nx.MultiDiGraph | nx.DiGraph) -> dict:
    """Return basic network statistics."""
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "density": round(nx.density(G), 6),
        "weakly_connected_components": nx.number_weakly_connected_components(G),
        "node_types": _count_node_types(G),
    }


def _count_node_types(G: nx.MultiDiGraph | nx.DiGraph) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, attrs in G.nodes(data=True):
        t = attrs.get("canonical_node_type", attrs.get("node_type", "other"))
        counts[t] = counts.get(t, 0) + 1
    return counts
