"""
Build capped UI artifact bundles per anchor for the Class 1 Streamlit app.

Reads rolling baselines + GAD-NR scores; never opens Excel.

Run from repo root:
  python -m class_1_anomaly_detection.src.experiments.build_ui_artifacts --anchor-month 202605
  python -m class_1_anomaly_detection.src.experiments.build_ui_artifacts --all-anchors
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_1_anomaly_detection.src.experiments.pygod_common import (
    OUTPUT_DIR,
    list_available_anchor_months,
    normalize_anchor_month,
    rolling_ml_dir,
    rolling_output_dir,
    write_json,
)

UI_ROOT = OUTPUT_DIR / "ui"
PRODUCTION_SLUG = "gadnr"
EGO_NODE_CAP = 80
EGO_EDGE_CAP = 200
TOP_N_BC = 60
REVIEW_TOP_N = 200

# Manual shock calendar (edit as needed). Months are YYYYMM.
DEFAULT_EVENTS = [
    {
        "id": "covid_wave_example",
        "label": "External demand shock (example)",
        "start_month": "202001",
        "end_month": "202212",
        "note": "Replace with curator-maintained events (strikes, pandemics, policy dates).",
    }
]

REASON_TEMPLATES = {
    "gnn_high": {
        "fact": "관계 AI(GAD-NR) 점수가 동일 기간 업체 분포에서 상위권입니다.",
        "interpretation": "학습된 유통 관계 패턴과 비교해 구조가 이례적으로 보입니다.",
        "question": "최근 거래 상대·품목 구성이 바뀌었는지 확인하시겠습니까?",
    },
    "bc_hub": {
        "fact": "매개 중심성(BC)이 높아 다수 경로의 허브로 관측됩니다.",
        "interpretation": "허브라는 사실만으로 위법이 확정되지 않습니다. 보조 지표입니다.",
        "question": "허브 역할이 사업 모델상 설명 가능한지 검토하시겠습니까?",
    },
    "price_flag": {
        "fact": "동일 품목·공급형태 대비 단가 편차(강건 z)가 높게 관측됩니다.",
        "interpretation": "가격 이상은 구조 이상과 별개일 수 있습니다.",
        "question": "단가 산정·보고 오류 가능성을 점검하시겠습니까?",
    },
    "timelag": {
        "fact": "공급일자와 최초접수일자 간 지연이 길게 관측됩니다.",
        "interpretation": "가납/수탁 의심 신호일 수 있으나 행정 지연일 수도 있습니다.",
        "question": "지연이 반복되는 거래처가 있는지 확인하시겠습니까?",
    },
}


def _ui_dir(anchor: str) -> Path:
    return UI_ROOT / f"anchor_{anchor}"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _build_graph(nodes: pd.DataFrame, edges: pd.DataFrame) -> nx.DiGraph:
    G = nx.DiGraph()
    for row in nodes.itertuples(index=False):
        G.add_node(
            str(row.entity_id),
            name=str(getattr(row, "name", "") or ""),
            node_type=str(getattr(row, "node_type", "other") or "other"),
        )
    for row in edges.itertuples(index=False):
        src, dst = str(row.src), str(row.dst)
        if src not in G or dst not in G:
            continue
        G.add_edge(
            src,
            dst,
            weight=float(getattr(row, "weight", 0) or 0),
            tx_count=int(getattr(row, "tx_count", 1) or 1),
        )
    return G


def _ego_payload(G: nx.DiGraph, entity_id: str, hops: int = 1) -> dict[str, Any]:
    if entity_id not in G:
        return {"entity_id": entity_id, "nodes": [], "edges": [], "truncated": False}
    nodes = {entity_id}
    frontier = {entity_id}
    for _ in range(max(1, hops)):
        nxt: set[str] = set()
        for n in frontier:
            nxt.update(G.predecessors(n))
            nxt.update(G.successors(n))
        nodes |= nxt
        frontier = nxt
        if len(nodes) >= EGO_NODE_CAP:
            break
    if len(nodes) > EGO_NODE_CAP:
        # Keep focal + highest-degree neighbors
        others = sorted(
            (n for n in nodes if n != entity_id),
            key=lambda n: G.degree(n),
            reverse=True,
        )
        nodes = {entity_id} | set(others[: EGO_NODE_CAP - 1])

    sub = G.subgraph(nodes).copy()
    edge_list = []
    for u, v, data in sub.edges(data=True):
        edge_list.append(
            {
                "src": u,
                "dst": v,
                "weight": float(data.get("weight", 0)),
                "tx_count": int(data.get("tx_count", 1)),
            }
        )
        if len(edge_list) >= EGO_EDGE_CAP:
            break

    node_list = [
        {
            "entity_id": n,
            "name": sub.nodes[n].get("name", ""),
            "node_type": sub.nodes[n].get("node_type", "other"),
            "degree": int(sub.degree(n)),
            "is_focal": n == entity_id,
        }
        for n in sub.nodes()
    ]
    return {
        "entity_id": entity_id,
        "hops": hops,
        "nodes": node_list,
        "edges": edge_list,
        "truncated": len(G.subgraph({entity_id} | set(G.predecessors(entity_id)) | set(G.successors(entity_id))))
        > len(node_list)
        or len(list(G.edges(entity_id))) + len(list(G.in_edges(entity_id))) > len(edge_list),
        "caps": {"nodes": EGO_NODE_CAP, "edges": EGO_EDGE_CAP},
    }


def _events_for_window(window_months: list[str]) -> list[dict[str, Any]]:
    if not window_months:
        return []
    start, end = min(window_months), max(window_months)
    hits = []
    for ev in DEFAULT_EVENTS:
        if ev["end_month"] >= start and ev["start_month"] <= end:
            hits.append(ev)
    return hits


def _evidence_for_row(row: pd.Series) -> dict[str, Any]:
    templates = []
    score = float(row.get(f"{PRODUCTION_SLUG}_score", 0) or 0)
    rank = int(row.get(f"{PRODUCTION_SLUG}_rank", 10**9) or 10**9)
    if rank <= 50 or score > 0:
        templates.append("gnn_high")
    bc = float(row.get("bc_score", 0) or 0)
    if bc > 0 and int(row.get("bc_rank", 10**9) or 10**9) <= 50:
        templates.append("bc_hub")
    if float(row.get("price_flag_rate", 0) or 0) >= 0.1:
        templates.append("price_flag")
    if float(row.get("median_lag_days", 0) or 0) >= 30:
        templates.append("timelag")
    if not templates:
        templates = ["gnn_high"]

    blocks = [REASON_TEMPLATES[t] for t in templates if t in REASON_TEMPLATES]
    return {
        "entity_id": str(row["entity_id"]),
        "template_ids": templates,
        "observed_facts": [b["fact"] for b in blocks],
        "interpretations": [b["interpretation"] for b in blocks],
        "next_questions": [b["question"] for b in blocks],
        "auxiliary": {
            "bc_score": bc,
            "bc_rank": int(row.get("bc_rank", 0) or 0) if not math.isnan(float(row.get("bc_rank", 0) or 0)) else 0,
            "price_flag_rate": float(row.get("price_flag_rate", 0) or 0),
            "median_lag_days": float(row.get("median_lag_days", 0) or 0),
            "gadnr_score": score,
            "gadnr_rank": rank if rank < 10**9 else None,
        },
    }


def build_ui_bundle(anchor_month: str, *, verbose: bool = True) -> Path:
    anchor = normalize_anchor_month(anchor_month)
    data_dir = rolling_output_dir(anchor)
    ml_dir = rolling_ml_dir(anchor)
    out_dir = _ui_dir(anchor)
    ego_dir = out_dir / "ego"
    out_dir.mkdir(parents=True, exist_ok=True)
    ego_dir.mkdir(parents=True, exist_ok=True)

    nodes = _read_csv(data_dir / "network_nodes.csv")
    edges = _read_csv(data_dir / "network_edges_firm.csv")
    if edges.empty:
        edges = _read_csv(data_dir / "network_edges.csv")
    bc = _read_csv(data_dir / "bc_per_entity.csv")
    price = _read_csv(data_dir / "price_zscore_per_entity.csv")
    timelag = _read_csv(data_dir / "timelag_per_entity.csv")
    scores = _read_csv(ml_dir / f"entity_anomaly_scores_{PRODUCTION_SLUG}.csv")
    if scores.empty:
        scores = _read_csv(OUTPUT_DIR / "ml" / f"entity_anomaly_scores_{PRODUCTION_SLUG}.csv")

    manifest_path = data_dir / "manifest.json"
    window_months: list[str] = []
    if manifest_path.exists():
        window_months = list(json.loads(manifest_path.read_text(encoding="utf-8")).get("window_months", []))

    if nodes.empty or edges.empty:
        raise FileNotFoundError(
            f"Missing network CSVs under {data_dir} — run run_graph_eda first."
        )
    if scores.empty:
        raise FileNotFoundError(
            f"Missing GAD-NR scores under {ml_dir} — run run_gadnr_production first."
        )

    review = scores.copy()
    review["entity_id"] = review["entity_id"].astype(str)
    if not bc.empty:
        bc = bc.copy()
        bc["entity_id"] = bc["entity_id"].astype(str)
        if "bc_rank" not in bc.columns:
            bc["bc_rank"] = bc["bc_score"].rank(ascending=False, method="min").astype(int)
        review = review.merge(bc[["entity_id", "bc_score", "bc_rank"]], on="entity_id", how="left", suffixes=("", "_bc"))
        if "bc_score_bc" in review.columns:
            review["bc_score"] = review["bc_score"].fillna(review["bc_score_bc"])
            review.drop(columns=["bc_score_bc"], inplace=True)
    if not price.empty:
        price = price.copy()
        price["entity_id"] = price["supplier_id"].astype(str)
        review = review.merge(
            price[["entity_id", "flag_rate"]].rename(columns={"flag_rate": "price_flag_rate"}),
            on="entity_id",
            how="left",
        )
    if not timelag.empty:
        timelag = timelag.copy()
        timelag["entity_id"] = timelag["supplier_id"].astype(str)
        cols = ["entity_id", "median_lag_days"]
        review = review.merge(timelag[cols], on="entity_id", how="left")

    rank_col = f"{PRODUCTION_SLUG}_rank"
    review = review.sort_values(rank_col).head(REVIEW_TOP_N)
    review.to_csv(out_dir / "review_list.csv", index=False, encoding="utf-8-sig")

    evidence = {}
    for _, row in review.iterrows():
        evidence[str(row["entity_id"])] = _evidence_for_row(row)
    write_json(out_dir / "entity_evidence.json", evidence)

    if not bc.empty:
        top = bc.nlargest(TOP_N_BC, "bc_score")
        overview = {
            "anchor_month": anchor,
            "metric": "bc_score",
            "note": "Discovery hub view only — not the AI review ranking.",
            "entities": top.assign(entity_id=top["entity_id"].astype(str))[
                [c for c in ["entity_id", "bc_score", "bc_rank", "name", "node_type"] if c in top.columns]
            ].to_dict(orient="records"),
        }
    else:
        overview = {"anchor_month": anchor, "metric": "bc_score", "entities": []}
    write_json(out_dir / "top_n_overview.json", overview)

    events = _events_for_window(window_months)
    write_json(out_dir / "events.json", {"anchor_month": anchor, "window_months": window_months, "events": events})

    G = _build_graph(nodes, edges)
    # Ego for review list + top BC entities
    ego_ids = set(review["entity_id"].astype(str).head(50)) | {
        str(e["entity_id"]) for e in overview.get("entities", [])[:30]
    }
    for eid in ego_ids:
        for hops in (1, 2):
            payload = _ego_payload(G, eid, hops=hops)
            write_json(ego_dir / f"{eid}_h{hops}.json", payload)

    watchlist_schema = {
        "description": "User-local soft watchlist (bookmarks / saved searches). No alerts.",
        "path_hint": "class_1_anomaly_detection/output/ui/watchlist_local.json",
        "fields": ["entity_id", "label", "saved_at", "anchor_month", "notes"],
        "items": [],
    }
    write_json(out_dir / "watchlist_schema.json", watchlist_schema)

    meta = {
        "anchor_month": anchor,
        "window_months": window_months,
        "production_model": PRODUCTION_SLUG,
        "review_rows": int(len(review)),
        "ego_entities": len(ego_ids),
        "ego_node_cap": EGO_NODE_CAP,
        "ego_edge_cap": EGO_EDGE_CAP,
        "disclaimer": "Internal policy-monitoring reference only. Not a sanction score.",
    }
    write_json(out_dir / "manifest.json", meta)
    if verbose:
        print(f"[ui] Wrote bundle → {out_dir.relative_to(_REPO_ROOT)}")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Class 1 UI artifact bundles")
    parser.add_argument("--anchor-month", type=str, default=None)
    parser.add_argument("--all-anchors", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.all_anchors:
        anchors = list_available_anchor_months()
    elif args.anchor_month:
        anchors = [normalize_anchor_month(args.anchor_month)]
    else:
        anchors = list_available_anchor_months()[-1:]

    if not anchors:
        raise SystemExit("No anchors found under output/rolling/")

    for a in anchors:
        try:
            build_ui_bundle(a, verbose=not args.quiet)
        except FileNotFoundError as exc:
            print(f"[skip] {a}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
