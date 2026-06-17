"""
Join-key definitions and key-cleaning utilities for the top7 data tier.
Class 3 — Impact Evaluation & Public Report.

CRITICAL: Keys are object/string type in top7 for this agent's data view.
The .0 suffix blocker causes 0% join without stripping — mandatory per EDA.
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

# Class 3 MCDM column references
COL_ITEM_GROUP: str = "품목군"
COL_ITEM_NAME: str = "품목명"
COL_DEVICE_CLASS: str = "등급"
COL_IMPLANTABLE: str = "인체이식 의료기기 여부"
COL_TRACEABLE: str = "추적관리대상 의료기기 여부"
COL_ORPHAN: str = "희소의료기기 여부"
COL_HOSPITAL_CODE: str = "요양기관기호(의료기관)"
COL_RECEIVER_NAME: str = "공급받은자"
COL_AMOUNT: str = "공급금액"
COL_SUPPLIER_NAME: str = "공급자"
COL_SUPPLIER_REG: str = "사업자등록번호"


def strip_float_suffix(series: pd.Series) -> pd.Series:
    """Remove '.0' float-string suffixes. CRITICAL for Class 3 — causes 0% join without."""
    if pd.api.types.is_integer_dtype(series):
        return series
    if pd.api.types.is_float_dtype(series):
        return series.astype("Int64").astype(str)
    return series.astype(str).str.strip().str.removesuffix(".0")


def prepare_master_keys(master: pd.DataFrame) -> pd.DataFrame:
    out = master.copy()
    for src, dst in zip(MASTER_KEYS, _JOIN_COLS_CANONICAL):
        out[dst] = strip_float_suffix(out[src])
    return out


def prepare_supply_keys(supply: pd.DataFrame) -> pd.DataFrame:
    out = supply.copy()
    for src, dst in zip(SUPPLY_KEYS, _JOIN_COLS_CANONICAL):
        out[dst] = strip_float_suffix(out[src])
    return out


def join_master_supply(
    master: pd.DataFrame,
    supply: pd.DataFrame,
    *,
    how: str = "inner",
) -> pd.DataFrame:
    """3-key composite join — mandatory. Without .0 stripping, Class 3 gets 0% match."""
    m = prepare_master_keys(master)
    s = prepare_supply_keys(supply)
    joined = s.merge(m, on=_JOIN_COLS_CANONICAL, how=how, suffixes=("", "_m"))
    return joined.drop(columns=_JOIN_COLS_CANONICAL)
