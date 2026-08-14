"""Pure Class 1 graph, GAD-NR, comparison, and evidence contracts.

Only an already validated monthly fact is accepted.  Optional ML dependencies
are imported by :func:`run_gadnr`, never while importing this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import json
import random
from typing import Any, Callable, Iterable

import networkx as nx
import numpy as np
import pandas as pd

from data_pipeline.contracts.supply_monthly import validate_monthly_fact

ROLE_VOCABULARY = (
    "manufacturer", "importer", "distributor", "hospital", "other",
    "multi_role", "unknown",
)
EXCLUDED_FEATURES = (
    "bc", "price_zscore", "price_flag", "time_lag", "hhi", "pdi",
    "edge_attr", "company_name", "unique_udi_count",
)
FEATURE_VERSION = "c1-gadnr-v2"
PIPELINE_SCHEMA_VERSION = "1.0.0"
_RATE_SCALE = Decimal("0.000001")
_LOG_CLIP_MAX = Decimal("1e100")
_BC_DEFAULTS = {
    "minimum_reachable_pairs": 1,
    "exact_pair_limit": 10_000,
    "maximum_pair_limit": 100_000,
    "sample_pairs": 10_000,
}
_QUANTITY_FIELDS = (
    ("amount", "amount_sum_clean", "amount_valid_row_count"),
    ("raw_supply_qty", "raw_supply_qty_sum", "raw_supply_qty_valid_row_count"),
    ("piece_qty", "piece_qty_sum", "piece_qty_valid_row_count"),
)


@dataclass(frozen=True)
class ModelGraph:
    anchor_month: str
    window_months: tuple[str, ...]
    nodes: tuple[str, ...]
    edges: pd.DataFrame
    self_loop_count: int


@dataclass(frozen=True)
class Class1PipelineResult:
    graph: ModelGraph
    features: pd.DataFrame
    qa_results: pd.DataFrame
    service_results: pd.DataFrame
    previous_anchor_diff: dict[str, dict[str, Any]]
    prior_nonoverlap_3m_diff: dict[str, dict[str, Any]]
    bc_evidence: dict[str, dict[str, Any]]
    manifest: dict[str, Any]


def _period(value: str) -> pd.Period:
    try:
        period = pd.Period(value, freq="M")
    except (TypeError, ValueError) as exc:
        raise ValueError("anchor_month must be a valid YYYYMM") from exc
    if period.strftime("%Y%m") != value:
        raise ValueError("anchor_month must be a valid YYYYMM")
    return period


def _months(anchor: str, count: int = 3) -> tuple[str, ...]:
    if count < 1:
        raise ValueError("window_months must be positive")
    end = _period(anchor)
    return tuple((end - offset).strftime("%Y%m") for offset in reversed(range(count)))


def _shift_month(anchor: str, offset: int) -> str:
    return (_period(anchor) + offset).strftime("%Y%m")


def _present(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip().casefold() for value in values
                         if pd.notna(value) and str(value).strip()}))


def _role(values: Iterable[Any]) -> str:
    materialized = tuple(values)
    if any(pd.isna(value) or not str(value).strip() for value in materialized):
        return "unknown"
    present = _present(materialized)
    allowed = tuple(value for value in present if value in ROLE_VOCABULARY[:5])
    if len(allowed) > 1 or len(present) > len(allowed):
        return "multi_role"
    return allowed[0] if allowed else "unknown"


def _dimension(values: Iterable[Any]) -> tuple[str | None, bool]:
    materialized = tuple(values)
    present = _present(materialized)
    has_missing = any(pd.isna(value) or not str(value).strip() for value in materialized)
    return (present[0], False) if len(present) == 1 and not has_missing else (None, True)


def _decimal_sum(frame: pd.DataFrame, field: str) -> Decimal:
    return sum((value for value in frame[field] if pd.notna(value)), Decimal("0"))


def _decimal_sum_nullable(frame: pd.DataFrame, field: str) -> Decimal | None:
    values = [value for value in frame[field] if pd.notna(value)]
    return sum(values, Decimal("0")) if values else None


def _rate(valid: int, total: int) -> Decimal:
    if total == 0:
        return Decimal("0.000000")
    return (Decimal(valid) / Decimal(total)).quantize(_RATE_SCALE, rounding=ROUND_HALF_EVEN)


def _safe_log1p(value: Decimal | int) -> float:
    """Convert only the bounded logarithm, never an unbounded Decimal total."""
    decimal = value if isinstance(value, Decimal) else Decimal(value)
    if decimal < 0:
        raise ValueError("log features require non-negative values")
    bounded = min(decimal, _LOG_CLIP_MAX)
    with localcontext() as context:
        context.prec = 50
        return float((Decimal(1) + bounded).ln())


def build_model_graph(
    fact: pd.DataFrame, *, anchor_month: str, window_months: int = 3,
) -> ModelGraph:
    """Collapse product rows to one directed edge for each company pair."""
    validate_monthly_fact(fact)
    window = _months(anchor_month, window_months)
    scoped = fact.loc[fact["month"].isin(window)].copy()
    loop_mask = scoped["src_company_id"].eq(scoped["dst_company_id"])
    self_loop_count = int(loop_mask.sum())
    scoped = scoped.loc[~loop_mask]
    records: list[dict[str, Any]] = []
    for (src, dst), group in scoped.groupby(
        ["src_company_id", "dst_company_id"], sort=True, observed=True,
    ):
        tx_count = int(group["tx_count"].sum())
        record: dict[str, Any] = {
            "src_company_id": str(src), "dst_company_id": str(dst),
            "tx_count": tx_count,
            "unique_product_count": int(group["product_id"].nunique()),
            "active_month_count": int(group["month"].nunique()),
        }
        for prefix, value_field, valid_field in _QUANTITY_FIELDS:
            valid_count = int(group[valid_field].sum())
            record[value_field] = _decimal_sum_nullable(group, value_field)
            record[valid_field] = valid_count
            record[f"{prefix}_valid_rate"] = _rate(valid_count, tx_count)
        records.append(record)
    edge_columns = [
        "src_company_id", "dst_company_id", "tx_count", "unique_product_count",
        "active_month_count",
    ] + [column for prefix, value, valid in _QUANTITY_FIELDS
         for column in (value, valid, f"{prefix}_valid_rate")]
    edges = pd.DataFrame.from_records(records, columns=edge_columns)
    nodes = tuple(sorted(set(scoped["src_company_id"]) | set(scoped["dst_company_id"])))
    return ModelGraph(anchor_month, window, nodes, edges, self_loop_count)


def model_edge_index(graph: ModelGraph) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Create the sole legal GAD-NR topology using ``graph.nodes`` ordering."""
    node_positions = {node: index for index, node in enumerate(graph.nodes)}
    pairs = []
    for row in graph.edges.itertuples(index=False):
        if row.src_company_id not in node_positions or row.dst_company_id not in node_positions:
            raise ValueError("graph edge endpoint is absent from graph.nodes")
        pairs.append((node_positions[row.src_company_id], node_positions[row.dst_company_id]))
    if len(pairs) != len(set(pairs)):
        raise ValueError("ModelGraph must contain one edge per company pair")
    pairs.sort()
    return (tuple(src for src, _ in pairs), tuple(dst for _, dst in pairs))


def _counterparties(scoped: pd.DataFrame, entity: str) -> set[str]:
    incoming = set(scoped.loc[scoped["dst_company_id"].eq(entity), "src_company_id"])
    outgoing = set(scoped.loc[scoped["src_company_id"].eq(entity), "dst_company_id"])
    return incoming | outgoing


def build_gadnr_features(
    fact: pd.DataFrame,
    graph: ModelGraph,
    *,
    region_vocabulary: tuple[str, ...] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build numeric node features; evidence and edge attributes stay excluded."""
    validate_monthly_fact(fact)
    scoped = fact.loc[
        fact["month"].isin(graph.window_months)
        & ~fact["src_company_id"].eq(fact["dst_company_id"])
    ]
    prior_months = _months(_shift_month(graph.anchor_month, -1), len(graph.window_months))
    prior = fact.loc[
        fact["month"].isin(prior_months)
        & ~fact["src_company_id"].eq(fact["dst_company_id"])
    ]
    derived_regions = _present(pd.concat([scoped["supplier_region"], scoped["receiver_region"]]))
    vocabulary = tuple(sorted(region_vocabulary)) if region_vocabulary is not None else derived_regions
    rows: list[dict[str, Any]] = []
    metadata: dict[str, dict[str, Any]] = {}
    for entity in graph.nodes:
        outgoing = scoped.loc[scoped["src_company_id"].eq(entity)]
        incoming = scoped.loc[scoped["dst_company_id"].eq(entity)]
        combined = pd.concat([incoming, outgoing])
        tx_count = int(combined["tx_count"].sum())
        counterparties = _counterparties(scoped, entity)
        prior_counterparties = _counterparties(prior, entity)
        role = _role(pd.concat([outgoing["supplier_type"], incoming["receiver_type"]]))
        region, region_problem = _dimension(
            pd.concat([outgoing["supplier_region"], incoming["receiver_region"]])
        )
        row: dict[str, Any] = {
            "entity_id": entity,
            "in_counterparty_count": int(incoming["src_company_id"].nunique()),
            "out_counterparty_count": int(outgoing["dst_company_id"].nunique()),
            "in_edge_count": int(incoming[["src_company_id", "dst_company_id"]].drop_duplicates().shape[0]),
            "out_edge_count": int(outgoing[["src_company_id", "dst_company_id"]].drop_duplicates().shape[0]),
            "in_product_diversity": int(incoming["product_id"].nunique()),
            "out_product_diversity": int(outgoing["product_id"].nunique()),
            "in_tx_log": _safe_log1p(int(incoming["tx_count"].sum())),
            "out_tx_log": _safe_log1p(int(outgoing["tx_count"].sum())),
            "tx_per_counterparty_log": _safe_log1p(Decimal(tx_count) / max(1, len(counterparties))),
            "active_month_count": int(combined["month"].nunique()),
            "prior_counterparty_count": len(prior_counterparties),
            "new_counterparty_count": len(counterparties - prior_counterparties),
            "lost_counterparty_count": len(prior_counterparties - counterparties),
            "region_missing_or_conflict": int(region_problem),
        }
        for prefix, value_field, valid_field in _QUANTITY_FIELDS:
            for direction, frame in (("in", incoming), ("out", outgoing)):
                direction_tx = int(frame["tx_count"].sum())
                valid_count = int(frame[valid_field].sum())
                row[f"{direction}_{prefix}_log"] = _safe_log1p(_decimal_sum(frame, value_field))
                row[f"{direction}_{prefix}_valid_row_count"] = valid_count
                row[f"{direction}_{prefix}_valid_rate"] = float(_rate(valid_count, direction_tx))
        row["piece_qty_per_tx_log"] = _safe_log1p(
            _decimal_sum(combined, "piece_qty_sum") / max(1, tx_count)
        )
        for value in vocabulary:
            row[f"region::{value}"] = int(not region_problem and region == value.casefold())
        for value in ROLE_VOCABULARY:
            row[f"role::{value}"] = int(role == value)
        rows.append(row)
        metadata[entity] = {
            "role_group": role,
            "region": region,
            "region_missing_or_conflict": region_problem,
        }
    features = (
        pd.DataFrame(rows).set_index("entity_id")
        if rows else pd.DataFrame(index=pd.Index([], name="entity_id"))
    )
    feature_order = list(features.columns)
    manifest = {
        "primary_model": "gadnr", "feature_version": FEATURE_VERSION,
        "feature_order": feature_order,
        "dtypes": {column: str(features[column].dtype) for column in feature_order},
        "role_vocabulary": list(ROLE_VOCABULARY),
        "region_vocabulary": list(vocabulary),
        "vocabulary_source": "configured" if region_vocabulary is not None else "derived",
        "production_ready": region_vocabulary is not None,
        "entity_metadata": metadata,
        "log_transform": {"method": "decimal_ln1p_then_float64", "clip_max": str(_LOG_CLIP_MAX)},
        "normalization": "none; counts, bounded log1p values, rates, and one-hot values are explicit",
        "excluded_features": list(EXCLUDED_FEATURES),
    }
    manifest["feature_fingerprint"] = _fingerprint({key: value for key, value in manifest.items() if key != "entity_metadata"})
    return features, manifest


def run_gadnr(
    features: pd.DataFrame,
    graph: ModelGraph,
    *,
    scorer: Callable[[pd.DataFrame, tuple[tuple[int, ...], tuple[int, ...]]], list[float]] | None = None,
    seed: int = 0,
) -> list[float]:
    """Score the graph using its own topology and deterministic node ordering."""
    if tuple(features.index.astype(str)) != graph.nodes:
        raise ValueError("feature rows must exactly match ModelGraph.nodes ordering")
    edge_index = model_edge_index(graph)
    random.seed(seed)
    np.random.seed(seed)
    if scorer is not None:
        scores = scorer(features, edge_index)
        if len(scores) != len(graph.nodes):
            raise ValueError("scorer must return one score per graph node")
        return [float(score) for score in scores]
    try:
        import torch
        from torch_geometric.data import Data
        from pygod.detector import GADNR
    except ImportError as exc:
        raise RuntimeError(
            "GAD-NR requires optional PyGOD/torch dependencies; install requirements-ml.txt."
        ) from exc
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    model = GADNR(num_layers=1, batch_size=0, epoch=100, random_state=seed)
    x = torch.tensor(features.to_numpy(dtype="float64"), dtype=torch.float32)
    edge = torch.tensor(edge_index, dtype=torch.long).reshape(2, -1).contiguous()
    model.fit(Data(x=x, edge_index=edge))
    return [float(value) for value in model.decision_score_]


def role_percentiles(scores: pd.DataFrame, *, minimum_sample: int = 30) -> pd.DataFrame:
    required = {"anchor_month", "role_group", "raw_score"}
    if not required.issubset(scores.columns):
        raise ValueError(f"scores must contain {sorted(required)}")
    result = scores.copy()
    result["role_group_sample_size"] = 0
    result["review_priority_percentile"] = pd.Series(pd.NA, index=result.index, dtype="Float64")
    result["insufficient_sample"] = False
    result["reason"] = pd.Series(pd.NA, index=result.index, dtype="string")
    for _, indices in result.groupby(["anchor_month", "role_group"], sort=True).groups.items():
        sample_size = len(indices)
        result.loc[indices, "role_group_sample_size"] = sample_size
        if sample_size < minimum_sample:
            result.loc[indices, "insufficient_sample"] = True
            result.loc[indices, "reason"] = "role_group_below_minimum_sample"
        else:
            result.loc[indices, "review_priority_percentile"] = (
                result.loc[indices, "raw_score"].rank(pct=True, method="average") * 100
            )
    return result


def _entity_windows(fact: pd.DataFrame, entity: str, months: tuple[str, ...]) -> pd.DataFrame:
    return fact.loc[
        fact["month"].isin(months)
        & (fact["src_company_id"].eq(entity) | fact["dst_company_id"].eq(entity))
        & ~fact["src_company_id"].eq(fact["dst_company_id"])
    ]


def build_anchor_diffs(
    fact: pd.DataFrame, *, anchor_month: str, entities: Iterable[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return overlapping relationship diff and non-overlapping volume diff."""
    validate_monthly_fact(fact)
    current_months = _months(anchor_month, 3)
    previous_months = _months(_shift_month(anchor_month, -1), 3)
    nonoverlap_months = _months(_shift_month(anchor_month, -3), 3)
    entity_ids = tuple(sorted(entities or (set(fact["src_company_id"]) | set(fact["dst_company_id"]))))
    relationship: dict[str, dict[str, Any]] = {}
    volume: dict[str, dict[str, Any]] = {}
    for entity in entity_ids:
        current = _entity_windows(fact, entity, current_months)
        previous = _entity_windows(fact, entity, previous_months)
        nonoverlap = _entity_windows(fact, entity, nonoverlap_months)
        current_cp = _counterparties(current, entity)
        previous_cp = _counterparties(previous, entity)
        relationship[entity] = {
            "current_months": current_months, "comparison_months": previous_months,
            "new_counterparty_ids": tuple(sorted(current_cp - previous_cp)),
            "retained_counterparty_ids": tuple(sorted(current_cp & previous_cp)),
            "lost_counterparty_ids": tuple(sorted(previous_cp - current_cp)),
        }
        record: dict[str, Any] = {
            "current_months": current_months, "comparison_months": nonoverlap_months,
            "tx_count_change": int(current["tx_count"].sum()) - int(nonoverlap["tx_count"].sum()),
            "product_count_change": int(current["product_id"].nunique()) - int(nonoverlap["product_id"].nunique()),
            "counterparty_count_change": len(current_cp) - len(_counterparties(nonoverlap, entity)),
        }
        for prefix, value_field, _ in _QUANTITY_FIELDS:
            record[f"{prefix}_change"] = _decimal_sum(current, value_field) - _decimal_sum(nonoverlap, value_field)
        volume[entity] = record
    return relationship, volume


def build_bc_evidence(
    graph: ModelGraph,
    entity_metadata: dict[str, dict[str, Any]],
    *,
    minimum_reachable_pairs: int = _BC_DEFAULTS["minimum_reachable_pairs"],
    exact_pair_limit: int = _BC_DEFAULTS["exact_pair_limit"],
    maximum_pair_limit: int = _BC_DEFAULTS["maximum_pair_limit"],
    sample_pairs: int = _BC_DEFAULTS["sample_pairs"],
    seed: int = 0,
) -> dict[str, dict[str, Any]]:
    """Compute fractional shortest-path gateway evidence, never a risk band."""
    network = nx.DiGraph()
    network.add_nodes_from(range(len(graph.nodes)))
    network.add_edges_from(zip(*model_edge_index(graph)))
    sources = [index for index, node in enumerate(graph.nodes)
               if entity_metadata.get(node, {}).get("role_group") in {"manufacturer", "importer"}]
    targets = [index for index, node in enumerate(graph.nodes)
               if entity_metadata.get(node, {}).get("role_group") == "hospital"]
    pair_count = len(sources) * len(targets)
    mode = "exact"
    if pair_count > maximum_pair_limit:
        mode = "deferred_too_large"
        selected_pairs: list[tuple[int, int]] = []
    elif pair_count > exact_pair_limit:
        mode = "deterministic_sample"
        selected_indices = random.Random(seed).sample(range(pair_count), min(sample_pairs, pair_count))
        selected_pairs = [
            (sources[index // len(targets)], targets[index % len(targets)])
            for index in selected_indices
        ]
    else:
        selected_pairs = [(source, target) for source in sources for target in targets]
    credit = {index: Decimal("0") for index in range(len(graph.nodes))}
    reachable_pairs = 0
    reachable_targets = {index: set() for index in range(len(graph.nodes))}
    if mode != "deferred_too_large":
        for source, target in selected_pairs:
            try:
                paths = list(nx.all_shortest_paths(network, source, target))
            except nx.NetworkXNoPath:
                continue
            reachable_pairs += 1
            fraction = Decimal(1) / Decimal(len(paths))
            for path in paths:
                for gateway in path[1:-1]:
                    credit[gateway] += fraction
                    reachable_targets[gateway].add(target)
    components = {}
    for component in nx.weakly_connected_components(network):
        for index in component:
            components[index] = len(component)
    insufficient = mode == "deferred_too_large" or reachable_pairs < minimum_reachable_pairs
    reason = (
        "graph_too_large" if mode == "deferred_too_large"
        else "no_reachable_source_target_pairs" if reachable_pairs == 0
        else "below_minimum_reachable_pairs" if insufficient else None
    )
    denominator = Decimal(reachable_pairs) if reachable_pairs else Decimal(1)
    return {
        node: {
            "bc_raw": credit[index],
            "gateway_share": (credit[index] / denominator),
            "weak_component_size": components.get(index, 1),
            "reachable_source_target_pairs": reachable_pairs,
            "reachable_target_count": len(reachable_targets[index]),
            "insufficient_evidence": insufficient,
            "mode": mode,
            "reason": reason,
        }
        for index, node in enumerate(graph.nodes)
    }


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def build_class1_pipeline(
    fact: pd.DataFrame,
    *,
    anchor_month: str,
    model_version: str,
    scorer: Callable[[pd.DataFrame, tuple[tuple[int, ...], tuple[int, ...]]], list[float]] | None = None,
    seed: int = 0,
    minimum_role_sample: int = 30,
    region_vocabulary: tuple[str, ...] | None = None,
) -> Class1PipelineResult:
    validate_monthly_fact(fact)
    graph = build_model_graph(fact, anchor_month=anchor_month)
    features, feature_manifest = build_gadnr_features(
        fact, graph, region_vocabulary=region_vocabulary,
    )
    scores = run_gadnr(features, graph, scorer=scorer, seed=seed)
    metadata = feature_manifest["entity_metadata"]
    qa = pd.DataFrame({
        "entity_id": graph.nodes,
        "anchor_month": anchor_month,
        "role_group": [metadata[node]["role_group"] for node in graph.nodes],
        "raw_score": scores,
    })
    ranked = role_percentiles(qa, minimum_sample=minimum_role_sample)
    previous, nonoverlap = build_anchor_diffs(fact, anchor_month=anchor_month, entities=graph.nodes)
    bc = build_bc_evidence(graph, metadata, seed=seed)
    service = ranked.drop(columns=["raw_score"]).copy()
    service["window_months"] = [graph.window_months] * len(service)
    service["model"] = "gadnr"
    service["model_version"] = model_version
    service["graph_summary"] = [
        {"node_count": len(graph.nodes), "edge_count": len(graph.edges), "self_loop_count": graph.self_loop_count}
    ] * len(service)
    service["previous_anchor_diff"] = [previous[node] for node in graph.nodes]
    service["prior_nonoverlap_3m_diff"] = [nonoverlap[node] for node in graph.nodes]
    service["bc_evidence"] = [bc[node] for node in graph.nodes]
    manifest = {
        "analysis_schema_version": PIPELINE_SCHEMA_VERSION,
        "primary_model": "gadnr", "model_version": model_version,
        "anchor_month": anchor_month, "window_months": graph.window_months,
        "seed": seed,
        "feature_version": FEATURE_VERSION,
        "feature_order": feature_manifest["feature_order"],
        "feature_fingerprint": feature_manifest["feature_fingerprint"],
        "feature_contract": {
            key: value for key, value in feature_manifest.items()
            if key != "entity_metadata"
        },
        "source_versions": sorted(str(value) for value in fact["source_version"].dropna().unique()),
        "graph_summary": {"node_count": len(graph.nodes), "edge_count": len(graph.edges), "self_loop_count": graph.self_loop_count},
        "edge_index_source": "model_graph_node_order",
        "model_config": {"num_layers": 1, "batch_size": 0, "epoch": 100, "seed": seed},
        "bc_config": {
            "seed": seed, "source_roles": ["manufacturer", "importer"],
            "target_roles": ["hospital"], **_BC_DEFAULTS,
        },
    }
    manifest["graph_fingerprint"] = _fingerprint({
        "nodes": graph.nodes,
        "edges": graph.edges.to_dict("records"),
        "window_months": graph.window_months,
    })
    manifest["manifest_fingerprint"] = _fingerprint(manifest)
    return Class1PipelineResult(graph, features, ranked, service, previous, nonoverlap, bc, manifest)


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if pd.isna(value) else float(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def serialize_service_results(rows: pd.DataFrame) -> list[dict[str, Any]]:
    """Serialize the service allow-list; raw scores and names cannot escape."""
    allowed = (
        "entity_id", "anchor_month", "window_months", "model", "model_version",
        "role_group", "role_group_sample_size", "review_priority_percentile",
        "insufficient_sample", "reason", "graph_summary", "previous_anchor_diff",
        "prior_nonoverlap_3m_diff", "bc_evidence",
    )
    columns = [column for column in allowed if column in rows]
    return [_json_value(row) for row in rows.loc[:, columns].to_dict("records")]


def serialize_class1_pipeline(result: Class1PipelineResult) -> dict[str, Any]:
    return _json_value({
        "analysis_schema_version": PIPELINE_SCHEMA_VERSION,
        "manifest": result.manifest,
        "service_results": serialize_service_results(result.service_results),
    })
