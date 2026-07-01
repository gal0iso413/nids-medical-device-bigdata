"""
Step 4 evaluation: compare GNN anomaly scores against Phase 1 rule-based signals.

Reads ``output/ml/entity_anomaly_scores_combined.csv`` plus Phase 1 metric CSVs,
computes overlap / correlation metrics, writes an evaluation report and an
enriched entity score table with baseline flags.

Run from repo root:
  python -m class_1_anomaly_detection.src.experiments.run_step4_evaluation --anchor-month 202605
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_1_anomaly_detection.src.experiments.pygod_common import (
    ML_OUTPUT_DIR,
    MODEL_LABELS,
    MODEL_SLUGS,
    list_available_anchor_months,
    list_evaluation_ready_anchor_months,
    normalize_anchor_month,
    rank_overlap,
    read_json,
    rolling_ml_dir,
    rolling_output_dir,
    spearman_corr,
    write_json,
)

TIMELAG_THRESHOLD_DAYS = 30
TOP_K_VALUES = (10, 50, 100)


def _load_combined_scores(anchor_month: str) -> pd.DataFrame:
    path = rolling_ml_dir(anchor_month) / "entity_anomaly_scores_combined.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path.relative_to(_REPO_ROOT)} — run run_pygod_compare first."
        )
    df = pd.read_csv(path)
    df["entity_id"] = df["entity_id"].astype(str)
    return df


def _build_baseline_flags(anchor_month: str) -> pd.DataFrame:
    """Entity-level Phase 1 risk flags for evaluation (not a ground-truth label set)."""
    out_dir = rolling_output_dir(anchor_month)
    nodes_path = out_dir / "network_nodes.csv"
    if not nodes_path.exists():
        raise FileNotFoundError("network_nodes.csv missing — run run_graph_eda.py first.")

    entities = pd.read_csv(nodes_path)
    entities["entity_id"] = entities["entity_id"].astype(str)
    base = entities[["entity_id", "name", "node_type"]].copy()

    bc_path = out_dir / "bc_per_entity.csv"
    if bc_path.exists():
        bc = pd.read_csv(bc_path)
        bc["entity_id"] = bc["entity_id"].astype(str)
        base = base.merge(
            bc[["entity_id", "bc_score", "in_degree", "out_degree", "high_risk"]],
            on="entity_id",
            how="left",
        )
        base["bc_high_risk"] = base["high_risk"].fillna(False).astype(bool)
    else:
        base["bc_score"] = 0.0
        base["bc_high_risk"] = False

    pz_path = out_dir / "price_zscore_per_entity.csv"
    if pz_path.exists():
        pz = pd.read_csv(pz_path)
        pz["entity_id"] = pz["supplier_id"].astype(str)
        base = base.merge(
            pz[
                [
                    "entity_id",
                    "flag_rate",
                    "median_zscore",
                    "max_zscore",
                    "high_risk",
                ]
            ].rename(columns={"high_risk": "price_high_risk"}),
            on="entity_id",
            how="left",
        )
        base["price_high_risk"] = base["price_high_risk"].fillna(False).astype(bool)
    else:
        base["price_high_risk"] = False

    lag_path = out_dir / "timelag_per_entity.csv"
    if lag_path.exists():
        lag = pd.read_csv(lag_path)
        lag["entity_id"] = lag["supplier_id"].astype(str)
        lag_col = "median_lag_days" if "median_lag_days" in lag.columns else "lag_days"
        base = base.merge(
            lag[["entity_id", lag_col]].rename(columns={lag_col: "median_lag_days"}),
            on="entity_id",
            how="left",
        )
        base["timelag_high"] = base["median_lag_days"].fillna(0) > TIMELAG_THRESHOLD_DAYS
    else:
        base["timelag_high"] = False

    hhi_path = out_dir / "hhi_per_hospital_group.csv"
    if hhi_path.exists():
        hhi = pd.read_csv(hhi_path)
        hhi["dominant_supplier_id"] = hhi["dominant_supplier_id"].astype(str)
        mono = hhi[hhi["concentration"] == "high"].groupby("dominant_supplier_id").agg(
            hhi_monopoly_pairs=("hospital_id", "count"),
            hhi_max_share=("dominant_supplier_share", "max"),
        )
        mono = mono.reset_index().rename(columns={"dominant_supplier_id": "entity_id"})
        base = base.merge(mono, on="entity_id", how="left")
        base["hhi_monopoly_pairs"] = base["hhi_monopoly_pairs"].fillna(0).astype(int)
        base["hhi_monopoly_flag"] = base["hhi_monopoly_pairs"] > 0
    else:
        base["hhi_monopoly_flag"] = False
        base["hhi_monopoly_pairs"] = 0

    base["baseline_any"] = (
        base["bc_high_risk"]
        | base["price_high_risk"]
        | base["timelag_high"]
        | base["hhi_monopoly_flag"]
    )
    return base


def _precision_at_k(
    scores: pd.Series, positive: pd.Series, k: int, *, subset: pd.Index | None = None
) -> float | None:
    if subset is not None:
        scores = scores.loc[scores.index.intersection(subset)]
        positive = positive.loc[positive.index.intersection(subset)]
    if len(scores) < k:
        return None
    top = set(scores.nlargest(k).index)
    pos_idx = set(positive.index[positive.astype(bool)])
    if not top:
        return None
    return round(len(top & pos_idx) / len(top), 4)


def _evaluate_model(
    df: pd.DataFrame,
    slug: str,
    baseline: pd.DataFrame,
) -> dict[str, Any]:
    score_col = f"{slug}_score"
    if score_col not in df.columns:
        return {"error": f"missing column {score_col}"}

    scores = df.set_index("entity_id")[score_col]
    base_idx = baseline.set_index("entity_id")

    common = scores.index.intersection(base_idx.index)
    scores = scores.loc[common]
    base_idx = base_idx.loc[common]

    dist_mask = base_idx["node_type"] == "distributor"
    dist_ids = base_idx.index[dist_mask]
    baseline_pos = base_idx["baseline_any"]
    bc_scores = base_idx["bc_score"].fillna(0.0)

    result: dict[str, Any] = {
        "model": MODEL_LABELS.get(slug, slug),
        "slug": slug,
        "flagged_nodes": int((df[f"{slug}_label"] == 1).sum()) if f"{slug}_label" in df.columns else None,
    }

    overlap_bc: dict[str, int] = {}
    overlap_baseline: dict[str, int] = {}
    for k in TOP_K_VALUES:
        overlap_bc[str(k)] = rank_overlap(scores, bc_scores, k=k)
        overlap_baseline[str(k)] = rank_overlap(scores, baseline_pos.astype(float), k=k)
    result["topk_overlap_bc"] = overlap_bc
    result["topk_overlap_baseline_any"] = overlap_baseline

    result["spearman"] = {
        "vs_bc_all": spearman_corr(scores, bc_scores),
        "vs_bc_distributors": spearman_corr(
            scores.loc[dist_ids], bc_scores.loc[dist_ids]
        ),
        "vs_baseline_any": spearman_corr(scores, baseline_pos.astype(float)),
    }

    if "flag_rate" in base_idx.columns:
        fr = base_idx["flag_rate"].fillna(0)
        result["spearman"]["vs_price_flag_rate"] = spearman_corr(scores, fr)
    if "median_lag_days" in base_idx.columns:
        lag = base_idx["median_lag_days"].fillna(0)
        result["spearman"]["vs_timelag"] = spearman_corr(scores, lag)

    precision: dict[str, float | None] = {}
    for k in TOP_K_VALUES:
        precision[f"all@{k}"] = _precision_at_k(scores, baseline_pos, k)
        precision[f"distributors@{k}"] = _precision_at_k(
            scores, baseline_pos, k, subset=dist_ids
        )
    result["baseline_precision"] = precision

    top_dist = (
        df[df["node_type"] == "distributor"]
        .nlargest(10, score_col)[
            ["entity_id", "name", score_col, "bc_score", "bc_rank"]
        ]
        .fillna("")
    )
    result["top10_distributors"] = top_dist.to_dict(orient="records")
    return result


def _score_model_for_recommendation(metrics: dict[str, Any]) -> float:
    """Higher is better — structural + baseline alignment for distributors."""
    bc50 = metrics.get("topk_overlap_bc", {}).get("50", 0)
    base50 = metrics.get("topk_overlap_baseline_any", {}).get("50", 0)
    prec50 = metrics.get("baseline_precision", {}).get("distributors@50") or 0.0
    rho_bc = metrics.get("spearman", {}).get("vs_bc_distributors") or 0.0
    rho_bc = max(0.0, rho_bc)
    return round(0.35 * bc50 + 0.25 * base50 + 0.25 * (prec50 * 50) + 0.15 * (rho_bc * 50), 2)


def _recommend_model(model_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        model_metrics.items(),
        key=lambda kv: _score_model_for_recommendation(kv[1]),
        reverse=True,
    )
    winner_slug, winner_metrics = ranked[0]
    return {
        "recommended_model": MODEL_LABELS.get(winner_slug, winner_slug),
        "recommended_slug": winner_slug,
        "recommendation_score": _score_model_for_recommendation(winner_metrics),
        "ranking": [
            {
                "slug": slug,
                "label": MODEL_LABELS.get(slug, slug),
                "score": _score_model_for_recommendation(m),
            }
            for slug, m in ranked
        ],
        "rationale": (
            "Weighted on top-50 BC overlap (35%), top-50 Phase-1-baseline overlap (25%), "
            "distributor precision@50 vs baseline_any (25%), and distributor Spearman vs BC (15%). "
            "Phase-1 baseline_any = BC p95 OR price p95 OR time-lag > 30d OR HHI monopoly dominant supplier."
        ),
    }


def _markdown_report(report: dict[str, Any]) -> str:
    window_months = report.get("window_months", []) or []
    window_text = (
        f"{window_months[0]} ~ {window_months[-1]}"
        if isinstance(window_months, list) and window_months
        else "n/a"
    )
    lines = [
        "# Step 4 — GNN vs Phase 1 Evaluation",
        "",
        f"Generated: {report.get('generated_at', '')}",
        f"Anchor month: {report.get('anchor_month', '')}",
        f"Rolling window: {window_text}",
        "",
        "## Recommendation",
        "",
        f"**{report['recommendation']['recommended_model']}** "
        f"(score {report['recommendation']['recommendation_score']})",
        "",
        report["recommendation"]["rationale"],
        "",
        "### Model ranking",
        "",
        "| Rank | Model | Score |",
        "|------|-------|-------|",
    ]
    for i, row in enumerate(report["recommendation"]["ranking"], 1):
        lines.append(f"| {i} | {row['label']} | {row['score']} |")

    lines.extend(["", "## Per-model metrics", ""])
    for slug, m in report["models"].items():
        lines.append(f"### {m['model']}")
        lines.append("")
        lines.append(f"- Flagged nodes: {m.get('flagged_nodes')}")
        lines.append(f"- Top-10 overlap with BC: {m['topk_overlap_bc'].get('10')}/10")
        lines.append(f"- Top-50 overlap with BC: {m['topk_overlap_bc'].get('50')}/50")
        lines.append(
            f"- Top-50 overlap with Phase-1 baseline_any: "
            f"{m['topk_overlap_baseline_any'].get('50')}/50"
        )
        lines.append(
            f"- Distributor precision@50 vs baseline_any: "
            f"{m['baseline_precision'].get('distributors@50')}"
        )
        sp = m.get("spearman", {})
        lines.append(
            f"- Spearman (distributors vs BC): {sp.get('vs_bc_distributors')}"
        )
        lines.append("")
        lines.append("Top-10 distributors:")
        lines.append("")
        lines.append("| Entity | Name | Score | BC |")
        lines.append("|--------|------|-------|-----|")
        for row in m.get("top10_distributors", [])[:10]:
            score_key = [k for k in row if k.endswith("_score")][0]
            lines.append(
                f"| {row.get('entity_id', '')} | {row.get('name', '')} | "
                f"{row.get(score_key, '')} | {row.get('bc_score', '')} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Baseline coverage",
            "",
            f"- Entities with any Phase-1 flag: {report['baseline_summary']['baseline_any_count']:,}",
            f"- BC high-risk: {report['baseline_summary']['bc_high_risk_count']:,}",
            f"- Price high-risk: {report['baseline_summary']['price_high_risk_count']:,}",
            f"- Time-lag > {TIMELAG_THRESHOLD_DAYS}d: {report['baseline_summary']['timelag_high_count']:,}",
            f"- HHI monopoly dominant: {report['baseline_summary']['hhi_monopoly_count']:,}",
            "",
            "## Interpretation notes",
            "",
            "- High global Spearman across GNN models is expected (similar ranking of all nodes).",
            "- Prefer **top-K overlap** and **distributor precision@K** for broker detection.",
            "- DOMINANT often ranks attribute outliers; AnomalyDAE/GAD-NR align better with BC.",
            "- OCGNN (one-class) and IsoForest (GAD-NR emb) test alternate anomaly-measure families.",
            "- No ground-truth labels — treat Phase-1 flags as weak pseudo-benchmarks only.",
            "",
        ]
    )
    return "\n".join(lines)


def run_step4_evaluation(
    *,
    anchor_month: str | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    anchor = normalize_anchor_month(anchor_month)
    combined = _load_combined_scores(anchor)
    baseline = _build_baseline_flags(anchor)
    window_months = []
    manifest = read_json(rolling_output_dir(anchor) / "manifest.json") or {}
    vals = manifest.get("window_months", [])
    if isinstance(vals, list):
        window_months = [str(v) for v in vals]

    available_slugs = [s for s in MODEL_SLUGS if f"{s}_score" in combined.columns]
    if not available_slugs:
        raise ValueError("No GNN score columns in combined CSV.")

    model_metrics = {
        slug: _evaluate_model(combined, slug, baseline) for slug in available_slugs
    }
    recommendation = _recommend_model(model_metrics)

    evaluated = combined.merge(
        baseline[
            [
                "entity_id",
                "bc_high_risk",
                "price_high_risk",
                "timelag_high",
                "hhi_monopoly_flag",
                "hhi_monopoly_pairs",
                "baseline_any",
                "flag_rate",
                "median_lag_days",
                "in_degree",
                "out_degree",
            ]
        ].drop_duplicates("entity_id"),
        on="entity_id",
        how="left",
    )
    rec_slug = recommendation["recommended_slug"]
    evaluated["recommended_model"] = recommendation["recommended_model"]
    evaluated["recommended_rank"] = evaluated[f"{rec_slug}_rank"]

    ml_dir = rolling_ml_dir(anchor)
    ml_dir.mkdir(parents=True, exist_ok=True)
    eval_csv = ml_dir / "entity_anomaly_scores_evaluated.csv"
    evaluated.sort_values(f"{rec_slug}_rank").to_csv(
        eval_csv, index=False, encoding="utf-8-sig"
    )

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "anchor_month": anchor,
        "window_months": window_months,
        "entities": int(len(evaluated)),
        "models_evaluated": available_slugs,
        "baseline_summary": {
            "baseline_any_count": int(baseline["baseline_any"].sum()),
            "bc_high_risk_count": int(baseline["bc_high_risk"].sum()),
            "price_high_risk_count": int(baseline["price_high_risk"].sum()),
            "timelag_high_count": int(baseline["timelag_high"].sum()),
            "hhi_monopoly_count": int(baseline["hhi_monopoly_flag"].sum()),
        },
        "models": model_metrics,
        "recommendation": recommendation,
        "outputs": {
            "evaluated_csv": str(eval_csv.relative_to(_REPO_ROOT)).replace("\\", "/"),
            "json": str((ml_dir / "step4_evaluation_report.json").relative_to(_REPO_ROOT)).replace("\\", "/"),
            "markdown": str((ml_dir / "step4_evaluation.md").relative_to(_REPO_ROOT)).replace("\\", "/"),
        },
    }

    json_path = ml_dir / "step4_evaluation_report.json"
    md_path = ml_dir / "step4_evaluation.md"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    md_path.write_text(_markdown_report(report), encoding="utf-8")

    if verbose:
        print("=" * 70)
        print("  Step 4 evaluation complete")
        print("=" * 70)
        print(f"  Anchor month          : {anchor}")
        if window_months:
            print(f"  Rolling window months : {window_months[0]} ~ {window_months[-1]}")
        print(f"  Entities evaluated     : {report['entities']:,}")
        print(f"  Phase-1 baseline_any   : {report['baseline_summary']['baseline_any_count']:,}")
        print(f"  Recommended model      : {recommendation['recommended_model']}")
        print(f"  Ranking:")
        for row in recommendation["ranking"]:
            print(f"    {row['label']:12s}  score={row['score']}")
        print(f"\n  Outputs:")
        print(f"    {eval_csv.relative_to(_REPO_ROOT)}")
        print(f"    {json_path.relative_to(_REPO_ROOT)}")
        print(f"    {md_path.relative_to(_REPO_ROOT)}")
        print("=" * 70)

    return report


def run_step4_evaluation_all_anchors(*, verbose: bool = True) -> dict[str, Any]:
    discovered = list_available_anchor_months()
    ready = list_evaluation_ready_anchor_months()
    skipped = [a for a in discovered if a not in set(ready)]
    reports: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    if verbose:
        print("=" * 70)
        print("  Step 4 evaluation - all anchors")
        print("=" * 70)
        if discovered:
            print(f"  Discovered anchors : {len(discovered)} ({discovered[0]} ~ {discovered[-1]})")
        else:
            print("  Discovered anchors : 0")
        print(f"  Evaluation-ready   : {len(ready)}")
        print(f"  Skipped            : {len(skipped)}")

    for anchor in ready:
        try:
            reports[anchor] = run_step4_evaluation(anchor_month=anchor, verbose=verbose)
        except Exception as exc:
            failures.append({"anchor_month": anchor, "error": str(exc)})
            if verbose:
                print(f"  [anchor {anchor}] failed: {exc}")

    compact = []
    for anchor, report in reports.items():
        rec = report.get("recommendation", {})
        compact.append(
            {
                "anchor_month": anchor,
                "window_months": report.get("window_months", []),
                "entities": report.get("entities"),
                "recommended_slug": rec.get("recommended_slug"),
                "recommended_model": rec.get("recommended_model"),
                "recommendation_score": rec.get("recommendation_score"),
                "output_report_json": report.get("outputs", {}).get("json"),
            }
        )

    summary: dict[str, Any] = {
        "mode": "all_anchors",
        "discovered_anchors": discovered,
        "evaluation_ready_anchors": ready,
        "skipped_missing_inputs": skipped,
        "success_count": len(reports),
        "failure_count": len(failures),
        "failures": failures,
        "anchors": compact,
    }
    summary_path = ML_OUTPUT_DIR / "step4_evaluation_all_anchors_summary.json"
    write_json(summary_path, summary)
    if verbose:
        print("\n" + "=" * 70)
        print("  All-anchor Step 4 summary")
        print("=" * 70)
        print(f"  Successes: {len(reports)}")
        print(f"  Failures : {len(failures)}")
        print(f"  Summary  : {summary_path.relative_to(_REPO_ROOT)}")
        print("=" * 70)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 4 evaluation for one anchor month")
    parser.add_argument(
        "--anchor-month",
        type=str,
        default=None,
        help="Anchor month YYYYMM. If omitted, use latest available anchor.",
    )
    parser.add_argument(
        "--all-anchors",
        action="store_true",
        help="Evaluate all evaluation-ready anchors.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.all_anchors and args.anchor_month is not None:
        parser.error("Use either --anchor-month or --all-anchors, not both.")
    if args.all_anchors:
        run_step4_evaluation_all_anchors(verbose=not args.quiet)
        return
    run_step4_evaluation(anchor_month=args.anchor_month, verbose=not args.quiet)


if __name__ == "__main__":
    main()
