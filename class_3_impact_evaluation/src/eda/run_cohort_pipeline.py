"""
Build anonymous cohort-dashboard UI artifacts for Class 3.

Rule-based cohorts only (업종 × 권역 × 품목군). No firm identifiers, no GNN scores.

Run from repo root:
  python -m class_3_impact_evaluation.src.eda.run_cohort_pipeline
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_3_impact_evaluation.src.ingest.keys import (
    COL_AMOUNT,
    COL_BASE_MONTH,
    COL_DEVICE_CLASS,
    COL_ITEM_GROUP,
    COL_ITEM_NAME,
    COL_LOCATION_SUPPLIER,
    COL_SUPPLIER_TYPE,
    COL_SUPPLY_CLASS,
    COL_SUPPLY_QTY,
)
from class_3_impact_evaluation.src.ingest.loader import REPO_ROOT

OUTPUT_DIR = REPO_ROOT / "class_3_impact_evaluation" / "output"
UI_DIR = OUTPUT_DIR / "ui"
CONFIG_PATH = REPO_ROOT / "class_3_impact_evaluation" / "config" / "cohort_config.json"

REGION_MAP = {
    "11": "수도권",
    "28": "수도권",
    "41": "수도권",
    # everything else treated as 비수도권 unless blank
}


def _prefer_load() -> pd.DataFrame:
    """Load supply from Class 1 parquet if available; else Class 3 Excel loader."""
    c1_parquet = (
        REPO_ROOT
        / "class_1_anomaly_detection"
        / "data"
        / "parquet"
        / "supply"
    )
    if c1_parquet.exists() and any(c1_parquet.glob("*.parquet")):
        frames = [pd.read_parquet(p) for p in sorted(c1_parquet.glob("*.parquet"))]
        print("[cohort] Using Class 1 Parquet supply partitions.")
        return pd.concat(frames, ignore_index=True)

    # Fall back: materialize via class 1 helper if possible
    try:
        from class_1_anomaly_detection.src.ingest.materialize_parquet import (
            load_top7_prefer_parquet,
        )

        _, supply = load_top7_prefer_parquet(verbose=True)
        return supply
    except Exception:
        from class_3_impact_evaluation.src.ingest.loader import load_supply

        supply, _ = load_supply(verbose=True)
        return supply


def _region_bucket(code: Any) -> str:
    s = str(code).strip().replace(".0", "") if pd.notna(code) else ""
    if not s or s.lower() in {"nan", "none"}:
        return "전국"
    return REGION_MAP.get(s, "비수도권")


def _hhi(shares: pd.Series) -> float:
    s = shares.astype(float)
    total = s.sum()
    if total <= 0:
        return 0.0
    p = s / total
    return float((p ** 2).sum())


def _ensure_config() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    example = CONFIG_PATH.with_suffix(".json.example")
    default = {
        "my_company_mode_enabled": False,
        "my_company_entity_id": None,
        "report_scope_device_classes": [1, 2, 3, 4],
        "disclaimer_ko": (
            "본 화면은 공급내역보고 기반 집계이며 실제 판매량이 아닙니다. "
            "회사명·순위·개인 식별 값은 제공하지 않습니다. "
            "보고 대상이 아닌 품목은 누락될 수 있습니다."
        ),
    }
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if example.exists():
        text = example.read_text(encoding="utf-8")
        CONFIG_PATH.write_text(text, encoding="utf-8")
        return json.loads(text)
    CONFIG_PATH.write_text(json.dumps(default, indent=2, ensure_ascii=False), encoding="utf-8")
    return default


def run_cohort_pipeline(*, verbose: bool = True) -> Path:
    cfg = _ensure_config()
    supply = _prefer_load()
    if COL_SUPPLY_CLASS in supply.columns:
        supply = supply[supply[COL_SUPPLY_CLASS].astype(str).str.strip() == "출고"].copy()

    supply["_region"] = (
        supply[COL_LOCATION_SUPPLIER].map(_region_bucket)
        if COL_LOCATION_SUPPLIER in supply.columns
        else "전국"
    )
    supply["_biz"] = (
        supply[COL_SUPPLIER_TYPE].astype(str).str.strip()
        if COL_SUPPLIER_TYPE in supply.columns
        else "기타"
    )
    supply["_group"] = (
        supply[COL_ITEM_GROUP].astype(str).str.strip()
        if COL_ITEM_GROUP in supply.columns
        else "unknown"
    )
    supply["_item"] = (
        supply[COL_ITEM_NAME].astype(str).str.strip()
        if COL_ITEM_NAME in supply.columns
        else "unknown"
    )
    supply["_month"] = (
        supply[COL_BASE_MONTH].astype(str).str.strip()
        if COL_BASE_MONTH in supply.columns
        else "unknown"
    )
    supply["_qty"] = pd.to_numeric(supply.get(COL_SUPPLY_QTY, 0), errors="coerce").fillna(0)
    supply["_amt"] = pd.to_numeric(supply.get(COL_AMOUNT, 0), errors="coerce").fillna(0)
    if COL_DEVICE_CLASS in supply.columns:
        supply["_class"] = pd.to_numeric(supply[COL_DEVICE_CLASS], errors="coerce")
    else:
        supply["_class"] = np.nan

    # Report-scope tag
    allowed = set(cfg.get("report_scope_device_classes") or [1, 2, 3, 4])
    supply["_in_report_scope"] = supply["_class"].isna() | supply["_class"].isin(allowed)

    UI_DIR.mkdir(parents=True, exist_ok=True)

    biz_types = sorted(supply["_biz"].dropna().unique().tolist())
    regions = ["수도권", "비수도권", "전국"]
    groups = sorted([g for g in supply["_group"].unique() if g and g != "nan"])[:80]

    filter_options = {
        "business_types": biz_types,
        "regions": regions,
        "product_groups": groups,
        "disclaimer_ko": cfg["disclaimer_ko"],
        "my_company_mode_enabled": bool(cfg.get("my_company_mode_enabled", False)),
    }
    (UI_DIR / "filter_options.json").write_text(
        json.dumps(filter_options, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Precompute cohort keys (biz, region, group) — sample top combinations by volume
    supply["_cohort_key"] = supply["_biz"] + "||" + supply["_region"] + "||" + supply["_group"]
    top_keys = (
        supply.groupby("_cohort_key")["_qty"].sum().nlargest(120).index.tolist()
    )

    cohorts: dict[str, Any] = {}
    maps: dict[str, Any] = {}
    for key in top_keys:
        part = supply[supply["_cohort_key"] == key]
        biz, region, group = key.split("||", 2)
        months = sorted(part["_month"].unique())
        monthly = (
            part.groupby("_month")
            .agg(tx_count=("_qty", "size"), qty=("_qty", "sum"), amount=("_amt", "sum"))
            .reset_index()
            .rename(columns={"_month": "month"})
        )
        # growth last vs prev
        growth = 0.0
        if len(monthly) >= 2:
            a, b = float(monthly.iloc[-2]["tx_count"]), float(monthly.iloc[-1]["tx_count"])
            growth = ((b - a) / a * 100.0) if a > 0 else 0.0

        # concentration among suppliers in cohort (by amount)
        if "공급자" in part.columns:
            shares = part.groupby("공급자")["_amt"].sum()
        else:
            shares = part.groupby("_biz")["_amt"].sum()
        hhi = _hhi(shares)
        n_items = int(part["_item"].nunique())
        n_tx = int(len(part))
        supplier_n = int(shares.shape[0])

        diagnosis = []
        if growth > 20 and hhi > 0.25:
            diagnosis.append("거래 활동이 늘면서 공급 집중도도 높습니다. 대체 조달 여부를 점검하세요.")
        elif growth < -20:
            diagnosis.append("최근 거래 활동이 크게 줄었습니다. 외부 이슈·보고 누락 가능성을 함께 보세요.")
        else:
            diagnosis.append("선택 기업군 집계가 준비되었습니다. 품목군 지도와 품목명 통계로 이어가세요.")

        cohorts[key] = {
            "business_type": biz,
            "region": region,
            "product_group": group,
            "cohort_size_proxy": supplier_n,
            "tx_count": n_tx,
            "item_name_count": n_items,
            "hhi": round(hhi, 4),
            "growth_pct": round(growth, 2),
            "monthly": monthly.to_dict(orient="records"),
            "diagnosis": diagnosis,
            "in_report_scope_share": round(float(part["_in_report_scope"].mean()), 4),
            "months": months,
        }

        # Map points: other groups in same biz+region
        sibling = supply[(supply["_biz"] == biz) & (supply["_region"] == region)]
        map_rows = []
        for g, gdf in sibling.groupby("_group"):
            sh = gdf.groupby("공급자")["_amt"].sum() if "공급자" in gdf.columns else gdf.groupby("_item")["_amt"].sum()
            m = (
                gdf.groupby("_month").size().sort_index()
            )
            g_growth = 0.0
            if len(m) >= 2:
                a, b = float(m.iloc[-2]), float(m.iloc[-1])
                g_growth = ((b - a) / a * 100.0) if a > 0 else 0.0
            map_rows.append(
                {
                    "product_group": g,
                    "hhi": round(_hhi(sh), 4),
                    "growth_pct": round(g_growth, 2),
                    "supplier_count": int(sh.shape[0]),
                    "selected": g == group,
                }
            )
        maps[f"{biz}||{region}"] = map_rows

    # Item-name stats (top items)
    item_stats = {}
    top_items = supply.groupby("_item")["_qty"].sum().nlargest(80).index.tolist()
    for item in top_items:
        idf = supply[supply["_item"] == item]
        group = str(idf["_group"].mode().iloc[0]) if not idf.empty else "unknown"
        monthly = (
            idf.groupby("_month")
            .agg(tx_count=("_qty", "size"), qty=("_qty", "sum"))
            .reset_index()
            .rename(columns={"_month": "month"})
        )
        item_stats[item] = {
            "item_name": item,
            "product_group": group,
            "tx_count": int(len(idf)),
            "qty_sum": float(idf["_qty"].sum()),
            "device_class_mode": (
                None
                if idf["_class"].isna().all()
                else float(idf["_class"].mode().iloc[0])
            ),
            "in_report_scope": bool(idf["_in_report_scope"].mean() >= 0.5),
            "monthly": monthly.to_dict(orient="records"),
        }

    (UI_DIR / "cohorts.json").write_text(
        json.dumps(cohorts, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (UI_DIR / "cohort_maps.json").write_text(
        json.dumps(maps, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (UI_DIR / "item_stats.json").write_text(
        json.dumps(item_stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    manifest = {
        "rows_supply": int(len(supply)),
        "n_cohorts": len(cohorts),
        "n_items": len(item_stats),
        "config": cfg,
        "note": "Anonymous aggregates only. No entity risk scores.",
    }
    (UI_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if verbose:
        print(f"[cohort] Wrote {len(cohorts)} cohorts, {len(item_stats)} items → {UI_DIR}")
    return UI_DIR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Class 3 cohort dashboard pipeline")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    run_cohort_pipeline(verbose=not args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
