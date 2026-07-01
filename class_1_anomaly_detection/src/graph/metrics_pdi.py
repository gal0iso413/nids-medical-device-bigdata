"""
Path Depth Index (PDI) — detect indirect supply and multi-stage detours.

Definition (spec §3 착수보고서):
  PDI per 3-key product composite (item_serial, model_serial, udi_serial) =
  max path length from any source node (in-degree=0 or type=manufacturer/importer)
  to any sink node (type=hospital) through edges carrying that product.

Regulatory threshold: PDI >= 3 triggers a high-risk indirect-supply flag.
"""
from __future__ import annotations

import pandas as pd
import networkx as nx

from ..ingest.keys import (
    filter_valid_supply_rows,
    classify_node_type,
    normalize_supply_entity_id,
    normalize_receiver_entity_id,
    strip_float_suffix,
    COL_SUPPLIER_SERIAL,
    COL_SUPPLIER_REG,
    COL_SUPPLIER_NAME,
    COL_SUPPLIER_TYPE,
    COL_RECEIVER_SERIAL,
    COL_RECEIVER_REG,
    COL_RECEIVER_NAME,
    COL_RECEIVER_TYPE,
    COL_HOSPITAL_CODE,
    COL_UDI,
    COL_ITEM_SERIAL,
    COL_MODEL_SERIAL,
    COL_UDI_SERIAL,
)

PDI_HIGH_RISK_THRESHOLD = 3
PDI_PATH_CUTOFF = 6

_SOURCE_TYPES = {"manufacturer", "importer"}
_SINK_TYPES = {"hospital"}


def _serial_str(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return strip_float_suffix(series).astype("Int64").astype(str)
    return series.astype(str).str.strip()


def _product_key_frame(df: pd.DataFrame) -> pd.DataFrame:
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


def _build_product_graph(df_product: pd.DataFrame) -> nx.DiGraph:
    """Build a directed graph for a single 3-key product composite."""
    G = nx.DiGraph()
    for row in df_product.itertuples(index=False):
        src = getattr(row, "_src_id", "unknown")
        dst = getattr(row, "_dst_id", "unknown")
        if src == "unknown" or dst == "unknown" or src == dst:
            continue
        src_type = getattr(row, "_src_type", "other")
        dst_type = getattr(row, "_dst_type", "other")
        if src not in G:
            G.add_node(src, node_type=src_type)
        if dst not in G:
            G.add_node(dst, node_type=dst_type)
        if not G.has_edge(src, dst):
            G.add_edge(src, dst)
    return G


def _prepare_pdi_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Precompute normalized ids and node types once for PDI grouping."""
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
    out["_src_type"] = out.apply(
        lambda r: classify_node_type(r.get(COL_SUPPLIER_TYPE)),
        axis=1,
    )
    out["_dst_type"] = out.apply(
        lambda r: classify_node_type(
            r.get(COL_RECEIVER_TYPE),
            hospital_code=r.get(COL_HOSPITAL_CODE),
        ),
        axis=1,
    )
    return out


def _max_source_to_sink_path(G: nx.DiGraph) -> int:
    """
    Return the length of the longest simple path from any source to any sink.
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
                for path in nx.all_simple_paths(G, src, snk, cutoff=PDI_PATH_CUTOFF):
                    max_len = max(max_len, len(path) - 1)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
    return max_len


def compute_pdi(
    supply: pd.DataFrame,
    *,
    master: pd.DataFrame | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Compute Path Depth Index for each unique 3-key product composite.

    Parameters
    ----------
    supply:
        Top7 supply DataFrame.
    master:
        Optional top7 master DataFrame for device-class enrichment.

    Returns
    -------
    pd.DataFrame with columns:
      - product_key, item_serial, model_serial, udi_di_serial, udi_di, pdi, ...
    """
    df = filter_valid_supply_rows(supply)
    df = _product_key_frame(df)

    required = {COL_ITEM_SERIAL, COL_MODEL_SERIAL, COL_UDI_SERIAL}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing product key columns: {sorted(missing)}")

    udi_class: dict[str, str] = {}
    if master is not None and COL_UDI in master.columns and "등급" in master.columns:
        for _, mrow in master[[COL_UDI, "등급"]].drop_duplicates().iterrows():
            udi_val = str(mrow[COL_UDI]).strip()
            grade = str(mrow["등급"]).strip() if pd.notna(mrow["등급"]) else ""
            if udi_val and grade:
                udi_class[udi_val] = grade

    df = _prepare_pdi_rows(df)
    records = []
    grouped = df.groupby("_product_key", sort=False)
    product_keys = grouped.size().index
    if verbose:
        print(f"[PDI] Computing for {len(product_keys)} unique 3-key product composites...")

    for product_key, df_product in grouped:
        G = _build_product_graph(df_product)
        pdi = _max_source_to_sink_path(G)

        udi_label = (
            str(df_product[COL_UDI].iloc[0]).strip()
            if COL_UDI in df_product.columns and df_product[COL_UDI].notna().any()
            else str(df_product["_udi_serial"].iloc[0])
        )

        unique_suppliers = int(df_product.loc[df_product["_src_id"] != "unknown", "_src_id"].nunique())
        unique_receivers = int(df_product.loc[df_product["_dst_id"] != "unknown", "_dst_id"].nunique())

        records.append({
            "product_key": product_key,
            "item_serial": df_product["_item_serial"].iloc[0],
            "model_serial": df_product["_model_serial"].iloc[0],
            "udi_di_serial": df_product["_udi_serial"].iloc[0],
            "udi_di": udi_label,
            "pdi": pdi,
            "high_risk": pdi >= PDI_HIGH_RISK_THRESHOLD,
            "device_class": udi_class.get(udi_label, float("nan")),
            "tx_count": len(df_product),
            "unique_suppliers": unique_suppliers,
            "unique_receivers": unique_receivers,
        })

    result = pd.DataFrame(records).sort_values("pdi", ascending=False)

    if verbose and len(result) > 0:
        high_risk_count = result["high_risk"].sum()
        print(
            f"[PDI] High-risk products (PDI≥{PDI_HIGH_RISK_THRESHOLD}): "
            f"{high_risk_count}/{len(result)} ({high_risk_count/len(result):.1%})"
        )
        print(
            result[
                ["product_key", "udi_di", "pdi", "high_risk", "device_class", "tx_count"]
            ].head(20).to_string(index=False)
        )

    return result


def pdi_summary(pdi_df: pd.DataFrame) -> dict:
    return {
        "total_products": len(pdi_df),
        "total_udis": len(pdi_df),  # backward-compat key for EDA summary
        "high_risk_count": int(pdi_df["high_risk"].sum()) if len(pdi_df) else 0,
        "high_risk_pct": round(float(pdi_df["high_risk"].mean()), 4) if len(pdi_df) else 0.0,
        "pdi_max": int(pdi_df["pdi"].max()) if len(pdi_df) else 0,
        "pdi_mean": round(float(pdi_df["pdi"].mean()), 2) if len(pdi_df) else 0.0,
        "pdi_median": int(pdi_df["pdi"].median()) if len(pdi_df) else 0,
        "distribution": pdi_df["pdi"].value_counts().sort_index().to_dict() if len(pdi_df) else {},
    }
