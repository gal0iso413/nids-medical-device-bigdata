"""
Price Margin Robust Z-Score — spec Phase 1 Robust Statistical Filter.

Spec mandate (착수보고서 §3 Phase 1):
  "Uses Median Absolute Deviation (MAD) and Robust Z-score instead of the mean
  to prevent margin averages from being skewed by extreme profiteers."

Formula:
  Z_robust = 0.6745 * (P - median(P)) / MAD(P)
  where MAD = median(|P - median(P)|)

Flag threshold from composite score formula (제안서 §3):
  I[Z_price > 2.0]  →  abnormal pricing detected

Grouping: per (품목명, 공급형태) to compare unit prices within the same product
and supply stage — prevents cross-product price mixing.

Output granularity: per-transaction flag, aggregated to per-entity summary for
downstream composite anomaly scoring.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..ingest.keys import (
    DISCARD_SUPPLY_CLASS,
    normalize_supply_entity_id,
    COL_SUPPLIER_SERIAL,
    COL_SUPPLIER_REG,
    COL_SUPPLIER_NAME,
    COL_SUPPLY_CLASS,
    COL_UNIT_PRICE,
    COL_ITEM_NAME,
    COL_ITEM_GROUP,
    COL_SUPPLY_TYPE,
)

PRICE_ZSCORE_THRESHOLD: float = 2.0
_MIN_GROUP_SIZE: int = 5   # minimum rows in a group to compute a meaningful Z-score


def _mad_zscore(prices: pd.Series) -> pd.Series:
    """
    Compute Robust Z-score using MAD for a price Series.
    Returns NaN for groups smaller than _MIN_GROUP_SIZE.
    """
    if len(prices) < _MIN_GROUP_SIZE:
        return pd.Series(np.nan, index=prices.index)
    med = prices.median()
    mad = (prices - med).abs().median()
    if mad == 0:
        # All prices identical — perfectly uniform, Z-score = 0
        return pd.Series(0.0, index=prices.index)
    return 0.6745 * (prices - med) / mad


def compute_price_zscore(
    supply: pd.DataFrame,
    *,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute per-transaction and per-entity price anomaly Z-scores.

    Parameters
    ----------
    supply:
        Top7 supply DataFrame (loaded + price-capped).

    Returns
    -------
    tx_df : pd.DataFrame
        Per-transaction rows with columns:
          - supplier_id, item_group, supply_type, unit_price,
            price_zscore, price_flag (True if |Z| > threshold)
    entity_df : pd.DataFrame
        Per-entity aggregation with columns:
          - supplier_id, supplier_name,
            flag_count, total_tx, flag_rate,
            median_zscore, max_zscore,
          - high_risk: True if entity is in top-5% by flag_rate
    """
    if COL_SUPPLY_CLASS in supply.columns:
        df = supply[supply[COL_SUPPLY_CLASS] != DISCARD_SUPPLY_CLASS].copy()
    else:
        df = supply.copy()

    # Require a valid positive unit price
    if COL_UNIT_PRICE not in df.columns:
        raise KeyError(f"Column '{COL_UNIT_PRICE}' not found in supply DataFrame.")

    df = df[df[COL_UNIT_PRICE].notna() & (df[COL_UNIT_PRICE] > 0)].copy()

    # Resolve entity IDs
    df["supplier_id"] = df.apply(
        lambda r: normalize_supply_entity_id(
            r.get(COL_SUPPLIER_SERIAL),
            r.get(COL_SUPPLIER_REG),
            r.get(COL_SUPPLIER_NAME),
        ),
        axis=1,
    )

    # Determine product grouping column (prefer 품목명 per spec HHI_item alignment)
    if COL_ITEM_NAME in df.columns and df[COL_ITEM_NAME].notna().mean() > 0.3:
        grp_col = COL_ITEM_NAME
    elif COL_ITEM_GROUP in df.columns and df[COL_ITEM_GROUP].notna().mean() > 0.3:
        grp_col = COL_ITEM_GROUP
    else:
        grp_col = None

    # Stage column for within-stage price comparison
    if COL_SUPPLY_TYPE in df.columns:
        stage_col = COL_SUPPLY_TYPE
    else:
        stage_col = None

    # Build grouping key
    group_keys: list[str] = []
    if grp_col:
        group_keys.append(grp_col)
    if stage_col:
        group_keys.append(stage_col)
    if not group_keys:
        df["_all"] = "all"
        group_keys = ["_all"]

    if verbose:
        print(f"[PriceZ] Grouping by: {group_keys}")
        print(f"[PriceZ] Rows with valid unit price: {len(df):,}")

    # Compute Z-score within each group
    zscore_parts: list[pd.Series] = []
    for _, grp in df.groupby(group_keys, sort=False):
        z = _mad_zscore(grp[COL_UNIT_PRICE])
        zscore_parts.append(z)
    df["price_zscore"] = pd.concat(zscore_parts).reindex(df.index)
    df["price_flag"] = df["price_zscore"].abs() > PRICE_ZSCORE_THRESHOLD

    # Build per-transaction output
    tx_cols = ["supplier_id"] + group_keys + [COL_UNIT_PRICE, "price_zscore", "price_flag"]
    if COL_SUPPLIER_NAME in df.columns:
        tx_cols = ["supplier_id", COL_SUPPLIER_NAME] + group_keys + [
            COL_UNIT_PRICE, "price_zscore", "price_flag"
        ]
    tx_df = df[[c for c in tx_cols if c in df.columns]].copy()
    tx_df = tx_df.rename(columns={COL_UNIT_PRICE: "unit_price"})

    # Per-entity aggregation
    entity_parts = []
    for eid, edf in df.groupby("supplier_id"):
        valid_z = edf["price_zscore"].dropna()
        entity_parts.append({
            "supplier_id": eid,
            "supplier_name": (
                str(edf[COL_SUPPLIER_NAME].iloc[0])
                if COL_SUPPLIER_NAME in edf.columns else ""
            ),
            "flag_count": int(edf["price_flag"].sum()),
            "total_tx": len(edf),
            "flag_rate": round(float(edf["price_flag"].mean()), 4),
            "median_zscore": round(float(valid_z.median()), 4) if len(valid_z) else float("nan"),
            "max_zscore": round(float(valid_z.abs().max()), 4) if len(valid_z) else float("nan"),
        })

    entity_df = pd.DataFrame(entity_parts)
    if len(entity_df):
        threshold_95 = entity_df["flag_rate"].quantile(0.95)
        entity_df["high_risk"] = entity_df["flag_rate"] >= threshold_95
        entity_df = entity_df.sort_values("flag_rate", ascending=False)

    if verbose:
        flagged = int(df["price_flag"].sum())
        flagged_pct = flagged / max(len(df), 1)
        hr = int(entity_df["high_risk"].sum()) if len(entity_df) else 0
        print(f"[PriceZ] Flagged transactions (|Z|>{PRICE_ZSCORE_THRESHOLD}): "
              f"{flagged:,}/{len(df):,} ({flagged_pct:.1%})")
        print(f"[PriceZ] High-risk entities (top-5% flag rate): {hr}")
        if len(entity_df):
            print(
                entity_df[["supplier_name", "flag_count", "total_tx", "flag_rate",
                            "median_zscore", "max_zscore"]]
                .head(20)
                .to_string(index=False)
            )

    return tx_df, entity_df


def price_zscore_summary(tx_df: pd.DataFrame, entity_df: pd.DataFrame) -> dict:
    return {
        "total_tx_evaluated": len(tx_df),
        "flagged_tx": int(tx_df["price_flag"].sum()),
        "flagged_tx_pct": round(float(tx_df["price_flag"].mean()), 4),
        "high_risk_entities": int(entity_df["high_risk"].sum()) if len(entity_df) else 0,
        "total_entities": len(entity_df),
        "zscore_threshold": PRICE_ZSCORE_THRESHOLD,
    }
