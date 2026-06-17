"""
Time-series EDA orchestrator — Class 2 Supply Forecast & Early Warning (Phase 1).

Builds the monthly supply index and rolling feature table from top7 data.
Validates key findings from eda_profile_2026-06-10-top7.md.

Phase 1 scope:
  - Monthly entity-level supply index (quantity + amount)
  - Rolling 3-month and 6-month windows
  - Gap detection (months with zero supply per entity)
  - 사용기한 (expiry date) distribution as survival proxy
  - Disruption threshold: 180-day silence flagged but NOT defined as final rule
    (PM decision deferred to Phase 2)
  - No survival model fitting; no Kaplan-Meier curves yet
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import numpy as np

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_2_supply_forecast.src.ingest.loader import load_top7, REPO_ROOT
from class_2_supply_forecast.src.ingest.keys import (
    join_master_supply,
    HOSPITAL_SUPPLY_TYPE,
    DISCARD_SUPPLY_CLASS,
    COL_SUPPLY_BASE_MONTH,
    COL_SUPPLY_DATE,
    COL_EXPIRY_DATE,
    COL_SUPPLY_QTY,
)

OUTPUT_DIR = REPO_ROOT / "class_2_supply_forecast" / "output"

_COL_SUPPLIER_REG = "사업자등록번호"
_COL_SUPPLIER_NAME = "공급자"
_COL_UDI = "UDI-DI"
_COL_SUPPLY_CLASS = "공급구분"
_COL_SUPPLY_TYPE = "공급형태"
_COL_AMOUNT = "공급금액"

DISRUPTION_GAP_DAYS = 180  # tentative; PM must validate before using in models


def _save_csv(df: pd.DataFrame, name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  [saved] {path.relative_to(REPO_ROOT)}")


def build_monthly_index(supply: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate supply into a monthly entity × product index.

    Groups by (supplier, UDI-DI, base month) and sums quantity and amount.
    Returns a tidy DataFrame suitable for rolling-window feature engineering.
    """
    df = supply.copy()
    if _COL_SUPPLY_CLASS in df.columns:
        df = df[df[_COL_SUPPLY_CLASS] != DISCARD_SUPPLY_CLASS]

    if COL_SUPPLY_BASE_MONTH not in df.columns:
        print(f"[timeseries] WARNING: '{COL_SUPPLY_BASE_MONTH}' not found. Skipping monthly index.")
        return pd.DataFrame()

    df["_ym"] = df[COL_SUPPLY_BASE_MONTH].astype(str).str[:6]
    df["_supplier"] = df.apply(
        lambda r: str(r.get(_COL_SUPPLIER_REG, "")).strip() or str(r.get(_COL_SUPPLIER_NAME, "")).strip(),
        axis=1,
    )

    group_cols = ["_supplier", _COL_UDI, "_ym"]
    agg = df.groupby(group_cols, dropna=False).agg(
        supply_qty=(COL_SUPPLY_QTY, "sum"),
        supply_amount=(_COL_AMOUNT, "sum"),
        tx_count=(COL_SUPPLY_QTY, "count"),
    ).reset_index()
    agg.rename(columns={"_supplier": "supplier_id", "_ym": "year_month"}, inplace=True)
    return agg.sort_values(["supplier_id", _COL_UDI, "year_month"])


def add_rolling_features(monthly: pd.DataFrame) -> pd.DataFrame:
    """Add 3m and 6m rolling mean supply qty and gap flag per (supplier, UDI-DI) series."""
    if monthly.empty:
        return monthly

    result_parts = []
    for (supplier, udi), grp in monthly.groupby(["supplier_id", "UDI-DI"]):
        grp = grp.sort_values("year_month").copy()
        qty = grp["supply_qty"]
        grp["rolling_3m_mean"] = qty.rolling(3, min_periods=1).mean().round(2)
        grp["rolling_6m_mean"] = qty.rolling(6, min_periods=1).mean().round(2)
        grp["zero_supply_month"] = qty == 0
        result_parts.append(grp)

    return pd.concat(result_parts, ignore_index=True)


def compute_expiry_profile(supply: pd.DataFrame) -> pd.DataFrame:
    """
    Profile 사용기한 (expiry date) distribution — survival proxy for Phase 2.

    Returns per-UDI-DI summary: null rate, earliest, latest expiry, shelf-life range.
    """
    if COL_EXPIRY_DATE not in supply.columns:
        print(f"[timeseries] WARNING: '{COL_EXPIRY_DATE}' not found.")
        return pd.DataFrame()

    df = supply[[_COL_UDI, COL_EXPIRY_DATE]].copy()
    df[COL_EXPIRY_DATE] = pd.to_datetime(df[COL_EXPIRY_DATE], format="%y%m%d", errors="coerce")

    profile = df.groupby(_COL_UDI)[COL_EXPIRY_DATE].agg(
        expiry_null_rate=lambda s: round(s.isna().mean(), 4),
        expiry_min=lambda s: s.min(),
        expiry_max=lambda s: s.max(),
        expiry_populated=lambda s: s.notna().sum(),
    ).reset_index()
    return profile


def flag_potential_disruptions(monthly: pd.DataFrame) -> pd.DataFrame:
    """
    Flag (supplier, UDI-DI) pairs that have a gap of >= DISRUPTION_GAP_DAYS.

    NOTE: This is exploratory only. The 180-day threshold is tentative; PM must
    validate the definition before using in any forecasting model.
    """
    if monthly.empty:
        return pd.DataFrame()

    monthly["_date"] = pd.to_datetime(monthly["year_month"], format="%Y%m", errors="coerce")
    records = []
    for (supplier, udi), grp in monthly.groupby(["supplier_id", "UDI-DI"]):
        grp_sorted = grp.sort_values("_date").dropna(subset=["_date"])
        if len(grp_sorted) < 2:
            continue
        dates = grp_sorted["_date"]
        gaps = dates.diff().dt.days.dropna()
        max_gap = int(gaps.max()) if len(gaps) > 0 else 0
        records.append({
            "supplier_id": supplier,
            "udi_di": udi,
            "max_gap_days": max_gap,
            "potential_disruption": max_gap >= DISRUPTION_GAP_DAYS,
            "observation_months": len(grp_sorted),
        })
    return pd.DataFrame(records).sort_values("max_gap_days", ascending=False)


def run_timeseries_eda() -> None:
    print("\n" + "=" * 70)
    print("  Class 2 — Phase 1 Time-Series EDA")
    print("=" * 70)

    print("\n[Step 1] Loading top7 workbooks...")
    master, supply = load_top7(verbose=True)

    print(f"\n[Step 2] Building monthly supply index...")
    monthly = build_monthly_index(supply)
    if not monthly.empty:
        print(f"  Monthly records: {len(monthly):,}")
        print(f"  Unique suppliers: {monthly['supplier_id'].nunique():,}")
        print(f"  Unique UDI-DIs: {monthly['UDI-DI'].nunique():,}")
        print(f"  Date range: {monthly['year_month'].min()} – {monthly['year_month'].max()}")
        monthly_features = add_rolling_features(monthly)
        _save_csv(monthly_features, "monthly_supply_index")
    else:
        print("  [SKIP] Monthly index could not be built — check 공급내역기준연월 column.")

    print("\n[Step 3] Profiling expiry dates (survival proxy)...")
    expiry_profile = compute_expiry_profile(supply)
    if not expiry_profile.empty:
        null_rate_overall = supply[COL_EXPIRY_DATE].isna().mean() if COL_EXPIRY_DATE in supply.columns else None
        print(f"  Overall 사용기한 null rate: {null_rate_overall:.1%}" if null_rate_overall is not None else "")
        print(expiry_profile.head(10).to_string(index=False))
        _save_csv(expiry_profile, "expiry_profile_per_udi")

    print("\n[Step 4] Flagging potential disruption gaps (exploratory, threshold=180d)...")
    if not monthly.empty:
        disruptions = flag_potential_disruptions(monthly)
        flagged = disruptions["potential_disruption"].sum()
        print(f"  Flagged pairs (gap≥{DISRUPTION_GAP_DAYS}d): {flagged}/{len(disruptions)}")
        print(f"  NOTE: 180-day threshold requires PM validation before use in models.")
        _save_csv(disruptions, "disruption_candidates")

    print("\n" + "=" * 70)
    print("  Phase 1 Time-Series EDA complete.")
    print("  Outputs saved to class_2_supply_forecast/output/")
    print("  Next: PM reviews → notify_phase_completion → HALT")
    print("=" * 70)


if __name__ == "__main__":
    run_timeseries_eda()
