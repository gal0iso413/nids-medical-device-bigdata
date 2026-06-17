"""
Join-key definitions and key-cleaning utilities for the top7 data tier.
Class 2 — Supply Forecast & Early Warning.

Keys are identical to Class 1; this module is kept isolated per agent governance.
The .0 suffix stripper is critical: Class 2 may read keys as object/string type.
"""
from __future__ import annotations

import pandas as pd

MASTER_KEYS: list[str] = [
    "의료기기품목일련번호",
    "모델일련번호",
    "UDIDI일련번호",
]

SUPPLY_KEYS: list[str] = [
    "의료기기품목일련번호",
    "모델일련번호",
    "UDI-DI 일련번호",
]

_JOIN_COLS_CANONICAL = ["_jk_item", "_jk_model", "_jk_udidi"]

PRICE_CAP_KRW: float = 50_000_000.0
HOSPITAL_SUPPLY_TYPE: str = "의료기관에 공급"
DISCARD_SUPPLY_CLASS: str = "폐기"
IMPORT_BUSINESS_TYPE: str = "수입업"

# Class 2 time-series column
COL_SUPPLY_BASE_MONTH: str = "공급내역기준연월"   # YYYYMM format
COL_SUPPLY_DATE: str = "공급일자"
COL_EXPIRY_DATE: str = "사용기한"
COL_SUPPLY_QTY: str = "공급수량"


def strip_float_suffix(series: pd.Series) -> pd.Series:
    """Remove '.0' float-string suffixes from a join key Series."""
    if pd.api.types.is_integer_dtype(series):
        return series
    if pd.api.types.is_float_dtype(series):
        return series.astype("Int64")
    return series.astype(str).str.strip().str.removesuffix(".0")


def prepare_master_keys(master: pd.DataFrame) -> pd.DataFrame:
    out = master.copy()
    for src, dst in zip(MASTER_KEYS, _JOIN_COLS_CANONICAL):
        out[dst] = strip_float_suffix(out[src]).astype(str)
    return out


def prepare_supply_keys(supply: pd.DataFrame) -> pd.DataFrame:
    out = supply.copy()
    for src, dst in zip(SUPPLY_KEYS, _JOIN_COLS_CANONICAL):
        out[dst] = strip_float_suffix(out[src]).astype(str)
    return out


def join_master_supply(
    master: pd.DataFrame,
    supply: pd.DataFrame,
    *,
    how: str = "inner",
) -> pd.DataFrame:
    """3-key composite join — mandatory to prevent row inflation."""
    m = prepare_master_keys(master)
    s = prepare_supply_keys(supply)
    joined = s.merge(m, on=_JOIN_COLS_CANONICAL, how=how, suffixes=("", "_m"))
    return joined.drop(columns=_JOIN_COLS_CANONICAL)
