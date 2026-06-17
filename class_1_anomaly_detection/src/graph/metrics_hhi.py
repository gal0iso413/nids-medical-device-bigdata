"""
Herfindahl-Hirschman Index (HHI) — detect special-relationship monopolies.

Spec definition (착수보고서 §2 Engineered Features):
  HHI_item = Σ s_i²  where s_i = supplier i's share of a specific medical
             institution's total purchases of a given item.

Spec alignment notes:
  - "item" in HHI_item refers to 품목명 (item name), NOT the broader 품목군
    administrative bucket (7 groups).  품목군 was previously used as default
    but is too coarse — any hospital buying even one item per group scores
    HHI = 1.0, making the indicator uninformative.
  - Grouping hierarchy: 품목명 → 품목군 → all_products.

Thresholds (spec §3 제안서):
  HHI > 0.25  → high concentration (monopoly risk)
  HHI > 0.15  → moderate concentration
  HHI ≤ 0.15 → competitive

Key design choice (PM-confirmed):
  - Filter to 공급형태 = 의료기관에 공급 (hospital segment only).
  - Exclude zero-price and null-price rows from amount-based share calculation.
  - Use 공급금액 (transaction amount) for market share; fall back to
    공급수량 × 공급단가 if 공급금액 is null.
"""
from __future__ import annotations

import pandas as pd

from ..ingest.keys import (
    HOSPITAL_SUPPLY_TYPE,
    DISCARD_SUPPLY_CLASS,
    normalize_supply_entity_id,
    normalize_receiver_entity_id,
    COL_SUPPLIER_SERIAL,
    COL_SUPPLIER_REG,
    COL_SUPPLIER_NAME,
    COL_RECEIVER_SERIAL,
    COL_RECEIVER_REG,
    COL_RECEIVER_NAME,
    COL_HOSPITAL_CODE,
    COL_SUPPLY_TYPE,
    COL_SUPPLY_CLASS,
    COL_AMOUNT,
    COL_UNIT_PRICE,
    COL_SUPPLY_QTY,
    COL_ITEM_NAME,
    COL_ITEM_GROUP,
)

HHI_HIGH_THRESHOLD = 0.25
HHI_MODERATE_THRESHOLD = 0.15


def _resolve_amount(row: pd.Series) -> float:
    """Return best available transaction amount for a row."""
    amt = row.get(COL_AMOUNT)
    if pd.notna(amt) and float(amt) > 0:
        return float(amt)
    price = row.get(COL_UNIT_PRICE)
    qty = row.get(COL_SUPPLY_QTY)
    if pd.notna(price) and pd.notna(qty) and float(price) > 0:
        return float(price) * float(qty)
    return 0.0


def _hhi_from_shares(amounts: pd.Series) -> float:
    total = amounts.sum()
    if total <= 0:
        return 0.0
    shares = amounts / total
    return float((shares ** 2).sum())


def compute_hhi(
    supply: pd.DataFrame,
    *,
    group_col: str | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Compute hospital-level HHI for each (hospital, item) pair.

    Spec alignment: the spec defines HHI_item per specific medical institution
    at item (품목명) level — not the broader 품목군 administrative bucket.
    Using 품목군 (7 buckets) caused near-100% saturation because every hospital
    buying a single product per group trivially scores HHI = 1.0.

    Parameters
    ----------
    supply:
        Top7 supply DataFrame.
    group_col:
        Product grouping column.  Defaults to 품목명 (item name, spec-aligned),
        falling back to 품목군 then all_products if absent.

    Returns
    -------
    pd.DataFrame with columns:
      - hospital_id: receiver entity identifier
      - hospital_name: receiver name
      - group: item name used for grouping
      - hhi: Herfindahl-Hirschman Index (0–1)
      - concentration: 'high' / 'moderate' / 'competitive'
      - dominant_supplier_id: supplier with largest share
      - dominant_supplier_share: share of dominant supplier
      - supplier_count: number of distinct suppliers
      - total_amount: total transaction amount for this hospital + item
    """
    df = supply.copy()
    if COL_SUPPLY_CLASS in df.columns:
        df = df[df[COL_SUPPLY_CLASS] != DISCARD_SUPPLY_CLASS]
    if COL_SUPPLY_TYPE in df.columns:
        df = df[df[COL_SUPPLY_TYPE] == HOSPITAL_SUPPLY_TYPE]

    df["_amount"] = df.apply(_resolve_amount, axis=1)
    df = df[df["_amount"] > 0]

    df["_hospital_id"] = df.apply(
        lambda r: normalize_receiver_entity_id(
            r.get(COL_RECEIVER_SERIAL),
            r.get(COL_RECEIVER_REG),
            r.get(COL_RECEIVER_NAME),
            hospital_code=r.get(COL_HOSPITAL_CODE),
        ),
        axis=1,
    )
    df["_supplier_id"] = df.apply(
        lambda r: normalize_supply_entity_id(
            r.get(COL_SUPPLIER_SERIAL),
            r.get(COL_SUPPLIER_REG),
            r.get(COL_SUPPLIER_NAME),
        ),
        axis=1,
    )

    df = df[df["_hospital_id"] != "unknown"]

    # Grouping: 품목명 first (spec "HHI_item"), then 품목군, then single bucket
    if group_col is None:
        if COL_ITEM_NAME in df.columns and df[COL_ITEM_NAME].notna().mean() > 0.3:
            group_col = COL_ITEM_NAME
        elif COL_ITEM_GROUP in df.columns and df[COL_ITEM_GROUP].notna().mean() > 0.3:
            group_col = COL_ITEM_GROUP
        else:
            group_col = "_all"
            df["_all"] = "all_products"

    if verbose:
        print(f"[HHI] Grouping by: {group_col}")
        print(f"[HHI] Hospital supply rows after filtering: {len(df):,}")

    records = []
    for (hosp_id, group_val), grp in df.groupby(["_hospital_id", group_col]):
        supplier_amounts = grp.groupby("_supplier_id")["_amount"].sum()
        hhi = _hhi_from_shares(supplier_amounts)
        dominant = supplier_amounts.idxmax()
        dom_share = round(supplier_amounts[dominant] / supplier_amounts.sum(), 4)

        hospital_name = grp[COL_RECEIVER_NAME].iloc[0] if COL_RECEIVER_NAME in grp.columns else ""

        if hhi > HHI_HIGH_THRESHOLD:
            concentration = "high"
        elif hhi > HHI_MODERATE_THRESHOLD:
            concentration = "moderate"
        else:
            concentration = "competitive"

        records.append({
            "hospital_id": hosp_id,
            "hospital_name": str(hospital_name),
            "group": group_val,
            "hhi": round(hhi, 4),
            "concentration": concentration,
            "dominant_supplier_id": dominant,
            "dominant_supplier_share": dom_share,
            "supplier_count": len(supplier_amounts),
            "total_amount": round(float(supplier_amounts.sum()), 0),
        })

    result = pd.DataFrame(records).sort_values("hhi", ascending=False)

    if verbose:
        high_count = (result["concentration"] == "high").sum()
        print(
            f"[HHI] High-concentration pairs (HHI>{HHI_HIGH_THRESHOLD}): "
            f"{high_count}/{len(result)} ({high_count/max(len(result),1):.1%})"
        )
        print(
            result[["hospital_name", "group", "hhi", "concentration",
                     "dominant_supplier_share", "supplier_count"]]
            .head(20)
            .to_string(index=False)
        )

    return result


def hhi_summary(hhi_df: pd.DataFrame) -> dict:
    return {
        "total_pairs": len(hhi_df),
        "high_concentration": int((hhi_df["concentration"] == "high").sum()),
        "moderate_concentration": int((hhi_df["concentration"] == "moderate").sum()),
        "competitive": int((hhi_df["concentration"] == "competitive").sum()),
        "hhi_max": round(float(hhi_df["hhi"].max()), 4),
        "hhi_mean": round(float(hhi_df["hhi"].mean()), 4),
        "hhi_median": round(float(hhi_df["hhi"].median()), 4),
        "unique_hospitals": hhi_df["hospital_id"].nunique(),
        "unique_groups": hhi_df["group"].nunique(),
    }
