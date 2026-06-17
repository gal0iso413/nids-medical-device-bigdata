"""
MCDM inputs EDA orchestrator — Class 3 Impact Evaluation (Phase 1).

Computes the core inputs for the Krajlic-style 4-quadrant portfolio map:
  X-axis (Supply Risk): HHI + Top-3 supplier share per product group
  Y-axis (Clinical Impact): unique hospital count per product group

Cross-referenced with master to add clinical severity flags:
  - Device class (등급)
  - Implantable status
  - Traceable status
  - Orphan device flag

Phase 1 scope:
  - Raw MCDM input vectors per product group; no scoring (weights are Phase 2)
  - Quadrant thresholds (P50 vs P75) deferred to Phase 2 Framework
  - No clustering (K-Means / GMM deferred to Phase 3 MVP)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import numpy as np

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_3_impact_evaluation.src.ingest.loader import load_top7, REPO_ROOT
from class_3_impact_evaluation.src.ingest.keys import (
    join_master_supply,
    HOSPITAL_SUPPLY_TYPE,
    DISCARD_SUPPLY_CLASS,
    COL_ITEM_GROUP,
    COL_ITEM_NAME,
    COL_DEVICE_CLASS,
    COL_IMPLANTABLE,
    COL_TRACEABLE,
    COL_ORPHAN,
    COL_HOSPITAL_CODE,
    COL_RECEIVER_NAME,
    COL_AMOUNT,
    COL_SUPPLIER_NAME,
    COL_SUPPLIER_REG,
)

OUTPUT_DIR = REPO_ROOT / "class_3_impact_evaluation" / "output"

_COL_SUPPLY_CLASS = "공급구분"
_COL_SUPPLY_TYPE = "공급형태"
HHI_HIGH = 0.25
HHI_MODERATE = 0.15


def _save_csv(df: pd.DataFrame, name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  [saved] {path.relative_to(REPO_ROOT)}")


def _resolve_group(row: pd.Series, group_col: str) -> str:
    """Return product group label; fall back to item name when group is null."""
    g = row.get(group_col)
    if pd.notna(g) and str(g).strip():
        return str(g).strip()
    n = row.get(COL_ITEM_NAME) or row.get(COL_ITEM_NAME + "_m")
    return str(n).strip() if pd.notna(n) and str(n).strip() else "unknown"


def _supplier_id(row: pd.Series) -> str:
    reg = row.get(COL_SUPPLIER_REG)
    name = row.get(COL_SUPPLIER_NAME)
    if pd.notna(reg) and str(reg).strip():
        return str(reg).strip()
    return f"name:{str(name).strip()}" if pd.notna(name) else "unknown"


def compute_supply_risk(supply: pd.DataFrame, joined: pd.DataFrame) -> pd.DataFrame:
    """
    Compute HHI and Top-3 supplier share per product group.
    Filters to hospital supply + valid amounts only.
    Falls back to 품목명 when 품목군 is null.
    """
    df = supply.copy()
    if _COL_SUPPLY_CLASS in df.columns:
        df = df[df[_COL_SUPPLY_CLASS] != DISCARD_SUPPLY_CLASS]
    if _COL_SUPPLY_TYPE in df.columns:
        df = df[df[_COL_SUPPLY_TYPE] == HOSPITAL_SUPPLY_TYPE]

    df = df[df[COL_AMOUNT].notna() & (df[COL_AMOUNT] > 0)].copy()
    df["_supplier_id"] = df.apply(_supplier_id, axis=1)

    # Resolve group — use supply 품목군 if available, else item name from supply
    group_col = COL_ITEM_GROUP if COL_ITEM_GROUP in df.columns else COL_ITEM_NAME
    df["_group"] = df.apply(lambda r: _resolve_group(r, group_col), axis=1)

    records = []
    for group_val, grp in df.groupby("_group"):
        supplier_amounts = grp.groupby("_supplier_id")[COL_AMOUNT].sum().sort_values(ascending=False)
        total = supplier_amounts.sum()
        if total <= 0:
            continue
        shares = supplier_amounts / total
        hhi = float((shares ** 2).sum())
        top3_share = float(shares.head(3).sum())
        supplier_count = len(supplier_amounts)
        records.append({
            "product_group": group_val,
            "hhi": round(hhi, 4),
            "hhi_label": "high" if hhi > HHI_HIGH else ("moderate" if hhi > HHI_MODERATE else "competitive"),
            "top3_supplier_share": round(top3_share, 4),
            "supplier_count": supplier_count,
            "total_supply_amount_krw": round(total, 0),
        })

    return pd.DataFrame(records).sort_values("hhi", ascending=False)


def compute_clinical_impact(supply: pd.DataFrame) -> pd.DataFrame:
    """
    Compute unique hospital count per product group (Y-axis of Krajlic matrix).
    Uses 요양기관기호 as hospital identifier; falls back to receiver name.
    """
    df = supply.copy()
    if _COL_SUPPLY_CLASS in df.columns:
        df = df[df[_COL_SUPPLY_CLASS] != DISCARD_SUPPLY_CLASS]
    if _COL_SUPPLY_TYPE in df.columns:
        df = df[df[_COL_SUPPLY_TYPE] == HOSPITAL_SUPPLY_TYPE]

    group_col = COL_ITEM_GROUP if COL_ITEM_GROUP in df.columns else COL_ITEM_NAME
    df["_group"] = df.apply(lambda r: _resolve_group(r, group_col), axis=1)

    def hosp_id(row):
        code = row.get(COL_HOSPITAL_CODE)
        if pd.notna(code) and str(code).strip():
            return str(code).strip()
        name = row.get(COL_RECEIVER_NAME)
        return str(name).strip() if pd.notna(name) else "unknown"

    df["_hosp_id"] = df.apply(hosp_id, axis=1)
    df = df[df["_hosp_id"] != "unknown"]

    impact = df.groupby("_group")["_hosp_id"].nunique().reset_index()
    impact.columns = ["product_group", "unique_hospital_count"]
    return impact.sort_values("unique_hospital_count", ascending=False)


def add_clinical_flags(supply_risk: pd.DataFrame, joined: pd.DataFrame) -> pd.DataFrame:
    """
    Join device-class clinical severity flags from master onto the supply risk table.
    """
    if joined.empty:
        return supply_risk

    group_col = COL_ITEM_GROUP if COL_ITEM_GROUP in joined.columns else COL_ITEM_NAME
    joined["_group"] = joined.apply(lambda r: _resolve_group(r, group_col), axis=1)

    flag_cols = [c for c in [COL_DEVICE_CLASS, COL_IMPLANTABLE, COL_TRACEABLE, COL_ORPHAN] if c in joined.columns]
    if not flag_cols:
        return supply_risk

    flags = joined.groupby("_group")[flag_cols].agg(
        lambda s: s.mode().iloc[0] if len(s.mode()) > 0 else None
    ).reset_index()
    flags.rename(columns={"_group": "product_group"}, inplace=True)

    return supply_risk.merge(flags, on="product_group", how="left")


def run_mcdm_eda() -> None:
    print("\n" + "=" * 70)
    print("  Class 3 — Phase 1 MCDM Inputs EDA")
    print("=" * 70)

    print("\n[Step 1] Loading top7 workbooks...")
    master, supply = load_top7(verbose=True)

    print("\n[Step 2] Joining master + supply (3-key composite, .0 strip applied)...")
    joined = join_master_supply(master, supply)
    print(f"  Joined rows: {len(joined):,} / {len(supply):,} ({len(joined)/len(supply):.1%})")

    print("\n[Step 3] Computing Supply Risk (HHI + Top-3 share) per product group...")
    supply_risk = compute_supply_risk(supply, joined)
    print(f"  Product groups: {len(supply_risk)}")
    high_hhi = (supply_risk["hhi_label"] == "high").sum()
    print(f"  High concentration (HHI>{HHI_HIGH}): {high_hhi}/{len(supply_risk)}")
    print(supply_risk.head(10).to_string(index=False))
    _save_csv(supply_risk, "supply_risk_per_group")

    print("\n[Step 4] Computing Clinical Impact (unique hospitals) per product group...")
    clinical = compute_clinical_impact(supply)
    print(f"  Product groups with hospital coverage: {len(clinical)}")
    print(f"  Total unique hospitals (overall): {supply['요양기관기호(의료기관)'].nunique() if '요양기관기호(의료기관)' in supply.columns else 'N/A'}")
    print(clinical.head(10).to_string(index=False))
    _save_csv(clinical, "clinical_impact_per_group")

    print("\n[Step 5] Adding clinical severity flags from master...")
    mcdm_inputs = supply_risk.merge(clinical, on="product_group", how="left")
    mcdm_inputs = add_clinical_flags(mcdm_inputs, joined)
    _save_csv(mcdm_inputs, "mcdm_inputs_combined")

    print("\n" + "=" * 70)
    print("  Phase 1 MCDM Inputs EDA Summary")
    print(f"  Supply risk: {len(mcdm_inputs)} product groups computed")
    print(f"  High HHI groups: {high_hhi}")
    print(f"  NOTE: Composite MCDM weights + quadrant thresholds deferred to Phase 2 Framework.")
    print("  Outputs saved to class_3_impact_evaluation/output/")
    print("  Next: PM reviews → notify_phase_completion → HALT")
    print("=" * 70)


if __name__ == "__main__":
    run_mcdm_eda()
