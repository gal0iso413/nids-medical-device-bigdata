"""Pure, monthly-fact based Class 1 GAD-NR preparation pipeline.

This module deliberately does not read files, import Streamlit, or import ML
packages at import time.  Its graph is one directed edge per company pair.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal
from math import log1p
from typing import Any, Callable

import pandas as pd

from data_pipeline.contracts.supply_monthly import validate_monthly_fact

ROLE_VOCABULARY = ("manufacturer", "importer", "distributor", "hospital", "other", "multi_role", "unknown")
EXCLUDED_FEATURES = ("bc", "price_zscore", "price_flag", "time_lag", "hhi", "pdi", "edge_attr", "company_name")

@dataclass(frozen=True)
class ModelGraph:
    anchor_month: str
    window_months: tuple[str, ...]
    nodes: tuple[str, ...]
    edges: pd.DataFrame
    self_loop_count: int

def _months(anchor: str, count: int = 3) -> tuple[str, ...]:
    periods = pd.period_range(anchor, periods=count, freq="M")
    return tuple(period.strftime("%Y%m") for period in periods)

def _role(values: pd.Series) -> str:
    present = sorted({str(value).strip().lower() for value in values if pd.notna(value) and str(value).strip()})
    allowed = [value for value in present if value in ROLE_VOCABULARY[:-2]]
    return allowed[0] if len(allowed) == 1 else "multi_role" if len(allowed) > 1 else "unknown"

def build_model_graph(fact: pd.DataFrame, *, anchor_month: str, window_months: int = 3) -> ModelGraph:
    """Aggregate one edge per (src_company_id, dst_company_id), never per product."""
    validate_monthly_fact(fact)
    window = _months(anchor_month, window_months)
    scoped = fact.loc[fact["month"].isin(window)].copy()
    loops = scoped["src_company_id"].eq(scoped["dst_company_id"])
    self_loop_count = int(loops.sum())
    scoped = scoped.loc[~loops]
    records: list[dict[str, Any]] = []
    for (src, dst), group in scoped.groupby(["src_company_id", "dst_company_id"], sort=True):
        def dec(column: str) -> Decimal | None:
            values = [value for value in group[column] if pd.notna(value)]
            return sum(values, Decimal("0")) if values else None
        records.append({"src_company_id": src, "dst_company_id": dst, "tx_count": int(group.tx_count.sum()),
            "amount_sum_clean": dec("amount_sum_clean"), "amount_valid_row_count": int(group.amount_valid_row_count.sum()),
            "raw_supply_qty_sum": dec("raw_supply_qty_sum"), "raw_supply_qty_valid_row_count": int(group.raw_supply_qty_valid_row_count.sum()),
            "piece_qty_sum": dec("piece_qty_sum"), "piece_qty_valid_row_count": int(group.piece_qty_valid_row_count.sum()),
            "unique_product_count": int(group.product_id.nunique()), "active_month_count": int(group.month.nunique())})
    edges = pd.DataFrame(records)
    nodes = tuple(sorted(set(scoped.src_company_id) | set(scoped.dst_company_id)))
    return ModelGraph(anchor_month, window, nodes, edges, self_loop_count)

def build_gadnr_features(fact: pd.DataFrame, graph: ModelGraph, *, region_vocabulary: tuple[str, ...] | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build deterministic node features; BC and edge attributes are excluded."""
    validate_monthly_fact(fact)
    scoped = fact.loc[fact.month.isin(graph.window_months) & ~fact.src_company_id.eq(fact.dst_company_id)]
    vocabulary = tuple(sorted(region_vocabulary or tuple(sorted({str(v) for v in pd.concat([scoped.supplier_region, scoped.receiver_region]) if pd.notna(v)}))))
    rows = []
    for entity in graph.nodes:
        out = scoped.loc[scoped.src_company_id.eq(entity)]; inn = scoped.loc[scoped.dst_company_id.eq(entity)]
        def total(frame: pd.DataFrame, field: str) -> Decimal:
            return sum((v for v in frame[field] if pd.notna(v)), Decimal("0"))
        def valid_rate(frame: pd.DataFrame, count: str) -> float:
            return float(frame[count].sum() / frame.tx_count.sum()) if int(frame.tx_count.sum()) else 0.0
        role = _role(pd.concat([out.supplier_type, inn.receiver_type]))
        row = {"entity_id": entity, "role_group": role,
            "in_counterparty_count": int(inn.src_company_id.nunique()), "out_counterparty_count": int(out.dst_company_id.nunique()),
            "in_edge_count": int(inn[["src_company_id", "dst_company_id"]].drop_duplicates().shape[0]), "out_edge_count": int(out[["src_company_id", "dst_company_id"]].drop_duplicates().shape[0]),
            "in_product_diversity": int(inn.product_id.nunique()), "out_product_diversity": int(out.product_id.nunique()),
            "in_tx_log": log1p(int(inn.tx_count.sum())), "out_tx_log": log1p(int(out.tx_count.sum())),
            "tx_per_counterparty": int((inn.tx_count.sum()+out.tx_count.sum()) / max(1, inn.src_company_id.nunique()+out.dst_company_id.nunique())),
            "in_amount_log": log1p(float(total(inn,"amount_sum_clean"))), "out_amount_log": log1p(float(total(out,"amount_sum_clean"))),
            "in_amount_valid_rate": valid_rate(inn,"amount_valid_row_count"), "out_amount_valid_rate": valid_rate(out,"amount_valid_row_count"),
            "in_raw_supply_qty_log": log1p(float(total(inn,"raw_supply_qty_sum"))), "out_raw_supply_qty_log": log1p(float(total(out,"raw_supply_qty_sum"))),
            "in_piece_qty_log": log1p(float(total(inn,"piece_qty_sum"))), "out_piece_qty_log": log1p(float(total(out,"piece_qty_sum"))),
            "piece_qty_per_tx_log": log1p(float(total(pd.concat([inn,out]),"piece_qty_sum")) / max(1,int(inn.tx_count.sum()+out.tx_count.sum()))),
            "active_month_count": int(pd.concat([inn.month,out.month]).nunique()), "prior_counterparty_count": 0, "new_counterparty_count": 0}
        for value in vocabulary: row[f"region::{value}"] = int(value in set(out.supplier_region.dropna()) or value in set(inn.receiver_region.dropna()))
        row["region_missing_or_conflict"] = int(not vocabulary)
        for value in ROLE_VOCABULARY: row[f"role::{value}"] = int(role == value)
        rows.append(row)
    frame = pd.DataFrame(rows).set_index("entity_id") if rows else pd.DataFrame(index=pd.Index([], name="entity_id"))
    manifest = {"primary_model":"gadnr", "feature_version":"c1-gadnr-v1", "feature_order":list(frame.columns), "dtypes":{c:str(frame[c].dtype) for c in frame}, "role_vocabulary":list(ROLE_VOCABULARY), "region_vocabulary":list(vocabulary), "vocabulary_source":"configured" if region_vocabulary else "derived", "production_ready":bool(region_vocabulary), "excluded_features":list(EXCLUDED_FEATURES)}
    return frame, manifest

def run_gadnr(features: pd.DataFrame, edge_index: list[tuple[int,int]], *, scorer: Callable[[pd.DataFrame, list[tuple[int,int]]], list[float]] | None = None, seed: int = 0) -> list[float]:
    """Run only injected scorer in tests; lazily import PyGOD otherwise."""
    if scorer: return scorer(features, edge_index)
    try:
        from pygod.detector import GADNR
    except ImportError as exc:
        raise RuntimeError("GAD-NR requires optional PyGOD/torch dependencies; install requirements-ml.txt.") from exc
    import torch
    model = GADNR(num_layers=1, batch_size=0, epoch=100, random_state=seed)
    x = torch.tensor(features.to_numpy(), dtype=torch.float32); edge = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
    model.fit(type("Data", (), {"x":x, "edge_index":edge})())
    return [float(v) for v in model.decision_score_]

def role_percentiles(scores: pd.DataFrame, *, minimum_sample: int = 30) -> pd.DataFrame:
    result = scores.copy(); result["review_priority_percentile"] = pd.NA; result["insufficient_sample"] = False
    for _, index in result.groupby("role_group", sort=True).groups.items():
        if len(index) < minimum_sample: result.loc[index,"insufficient_sample"] = True; continue
        result.loc[index,"review_priority_percentile"] = result.loc[index,"raw_score"].rank(pct=True, method="average") * 100
    return result

def serialize_service_results(rows: pd.DataFrame) -> list[dict[str, Any]]:
    """Never serialize raw scores or direct names/paths."""
    allowed = [c for c in ("entity_id","anchor_month","window_months","model","model_version","role_group","sample_size","review_priority_percentile","insufficient_sample","reason","graph_summary","diff_summary","bc_evidence") if c in rows]
    return [{key: (None if pd.isna(value) else value) for key,value in row[allowed].items()} for _,row in rows.iterrows()]
