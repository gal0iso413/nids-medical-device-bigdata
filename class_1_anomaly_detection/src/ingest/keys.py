"""
Join-key definitions and key-cleaning utilities for the top7 data tier.

3-key composite is MANDATORY (non-negotiable per top7 EDA):
- UDI-only join: +4.86% row inflation
- item+model-only join: +162.59% row inflation
Both are disqualifying for any downstream metric.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

_INVALID_REG_STRINGS = frozenset({"", "0", "0.0", "nan", "none", "null"})

# Master registration join key columns
MASTER_KEYS: list[str] = [
    "의료기기품목일련번호",
    "모델일련번호",
    "UDIDI일련번호",
]

# Supply transaction join key columns (note: UDI-DI serial name differs from master)
SUPPLY_KEYS: list[str] = [
    "의료기기품목일련번호",
    "모델일련번호",
    "UDI-DI 일련번호",
]

# Canonical join key name used after alignment
_JOIN_KEY_CANONICAL = "__join_key__"
_JOIN_COLS_CANONICAL = ["_jk_item", "_jk_model", "_jk_udidi"]

# Known duplicate column: pandas renames the second 업종 column (col CN) to 업종.1
MASTER_BUSINESS_TYPE_DETAILED = "업종.1"

# Price thresholds (from top7 EDA: barcode-in-price outlier confirmed)
PRICE_CAP_KRW: float = 50_000_000.0

# Supply destination for anomaly/HHI filtering (hospital segment)
HOSPITAL_SUPPLY_TYPE: str = "의료기관에 공급"

# Discard supply classification — receivers are always null; exclude from flow graphs
DISCARD_SUPPLY_CLASS: str = "폐기"

# Import proxy: manufacturer country (제조원국가) is 100% null in top7; use business type instead
IMPORT_BUSINESS_TYPE: str = "수입업"

# ---------------------------------------------------------------------------
# Entity identifier columns (spec §2 착수보고서 — Node list)
# Priority order: company serial (system-generated, always clean int)
#                 → business reg number (self-reported, may have .0 suffix)
#                 → hospital code (for medical-institution receivers)
#                 → company name (last resort)
# ---------------------------------------------------------------------------
# Supply side — supplier
COL_SUPPLIER_SERIAL: str = "공급한자 업체일련번호"   # col E, system serial
COL_SUPPLIER_REG: str = "사업자등록번호"              # col I, business reg
COL_SUPPLIER_NAME: str = "공급자"                     # col B, name

# Supply side — receiver
COL_RECEIVER_SERIAL: str = "공급받은자 업체일련번호" # col O, system serial
COL_RECEIVER_REG: str = "공급받은자 사업자등록번호"  # col Q, business reg
COL_RECEIVER_NAME: str = "공급받은자"                 # col J, name
COL_HOSPITAL_CODE: str = "요양기관기호(의료기관)"    # col K, institution symbol

# Time-lag columns (spec §2 착수보고서 — Engineered Features)
COL_SUPPLY_DATE: str = "공급일자"        # col AG, physical supply date
COL_FIRST_RECEIPT_DATE: str = "최초접수일자"  # col BR, admin receipt date

# Price columns
COL_UNIT_PRICE: str = "공급단가"   # col AK
COL_AMOUNT: str = "공급금액"       # col AL
COL_SUPPLY_QTY: str = "공급수량"   # col AH

# Device / product grouping
COL_ITEM_NAME: str = "품목명"      # col W — item name (spec HHI "item" level)
COL_ITEM_GROUP: str = "품목군"     # col BQ — broader admin group
COL_SUPPLY_TYPE: str = "공급형태"  # col G — supply destination
COL_SUPPLY_CLASS: str = "공급구분" # col F — issue/return/discard/lease/recall
COL_SUPPLIER_TYPE: str = "업종"    # col D — supplier business type
COL_RECEIVER_TYPE: str = "공급받은자업종"  # col M — receiver business type
COL_UDI: str = "UDI-DI"           # col AA


def normalize_reg_number(reg: Any) -> str | None:
    """
    Clean a business registration number for use as an entity ID.

    Handles float dtypes, '.0' string suffixes, and rejects placeholder values
    like ``0`` that appear when registration numbers are missing in source data.
    """
    if reg is None or (isinstance(reg, float) and pd.isna(reg)):
        return None
    if isinstance(reg, str) and pd.isna(reg):
        return None

    if isinstance(reg, (int, float)) and not isinstance(reg, bool):
        if float(reg) == 0.0:
            return None
        if isinstance(reg, float) and reg == int(reg):
            reg = int(reg)
        s = str(reg)
    else:
        s = str(reg).strip()
        if s.endswith(".0"):
            head = s[:-2]
            if head.replace("-", "").isdigit():
                s = head
        try:
            f = float(s)
            if f == 0.0:
                return None
            if f == int(f):
                s = str(int(f))
        except ValueError:
            pass

    s = s.strip()
    if s.lower() in _INVALID_REG_STRINGS:
        return None
    return s


def normalize_entity_id(reg: Any, name: Any) -> str:
    """
    Return a stable entity identifier; prefer cleaned business registration number.

    Falls back to ``name:{company_name}`` when registration is missing or invalid.
    """
    cleaned = normalize_reg_number(reg)
    if cleaned:
        return cleaned
    if name is not None and not (isinstance(name, float) and pd.isna(name)):
        if not pd.isna(name):
            n = str(name).strip()
            if n and n.lower() not in _INVALID_REG_STRINGS:
                return f"name:{n}"
    return "unknown"


def normalize_supply_entity_id(serial: Any, reg: Any, name: Any) -> str:
    """
    Resolve a supplier entity ID using the priority order from the spec (착수보고서 §2):
      1. ``공급한자 업체일련번호`` — system-generated company serial (always clean int)
      2. ``사업자등록번호``        — business registration number (may have .0 suffix)
      3. ``공급자``               — company name (last resort)

    Using company serial as priority directly fixes the .0-suffix fragmentation
    that caused 528 weakly-connected components in the first run.
    """
    s = normalize_reg_number(serial)
    if s:
        return f"co:{s}"
    return normalize_entity_id(reg, name)


def normalize_receiver_entity_id(
    serial: Any,
    reg: Any,
    name: Any,
    *,
    hospital_code: Any = None,
) -> str:
    """
    Resolve a receiver entity ID.

    Priority (spec §2 Nodes):
      1. ``요양기관기호(의료기관)`` — medical institution symbol (most stable for hospitals)
      2. ``공급받은자 업체일련번호`` — system company serial
      3. ``공급받은자 사업자등록번호`` — business reg number
      4. ``공급받은자``              — company name
    """
    if hospital_code is not None and pd.notna(hospital_code) and str(hospital_code).strip():
        code = normalize_reg_number(hospital_code) or str(hospital_code).strip()
        return f"hosp:{code}"
    s = normalize_reg_number(serial)
    if s:
        return f"co:{s}"
    return normalize_entity_id(reg, name)


def normalize_hospital_id(
    reg: Any,
    name: Any,
    *,
    hospital_code: Any = None,
) -> str:
    """
    Return a stable hospital identifier.

    Prefers ``요양기관기호(의료기관)`` when present (most reliable for dedup),
    then business registration number, then company name fallback.
    """
    if hospital_code is not None and pd.notna(hospital_code) and str(hospital_code).strip():
        code = normalize_reg_number(hospital_code) or str(hospital_code).strip()
        return f"hosp:{code}"
    return normalize_entity_id(reg, name)


def classify_node_type(business_type: Any, *, hospital_code: Any = None) -> str:
    """
    Classify an entity's business role from 업종 text and optional hospital code.

    ``요양기관기호(의료기관)`` presence is used as a hospital signal when 업종
    is null or uninformative — a data-quality enrichment, not a threshold change.
    """
    if hospital_code is not None and pd.notna(hospital_code) and str(hospital_code).strip():
        return "hospital"
    if pd.isna(business_type):
        return "unknown"
    s = str(business_type).strip()
    if "의료기관" in s:
        return "hospital"
    if "수입" in s:
        return "importer"
    if "제조" in s:
        return "manufacturer"
    if "판매" in s or "임대" in s or "도매" in s:
        return "distributor"
    return "other"


def strip_float_suffix(series: pd.Series) -> pd.Series:
    """
    Remove '.0' float-string suffixes from a Series that should be integer keys.

    When pandas reads integer columns from Excel as float64 and they are later
    cast to string for joining, values appear as '12345.0' instead of '12345'.
    This function normalises them defensively even when dtypes are already int.
    """
    if pd.api.types.is_integer_dtype(series):
        return series
    if pd.api.types.is_float_dtype(series):
        return series.astype("Int64")
    return (
        series.astype(str)
        .str.strip()
        .str.removesuffix(".0")
    )


def prepare_master_keys(master: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of master with the three join key columns normalised.
    Adds columns ``_jk_item``, ``_jk_model``, ``_jk_udidi`` as int64.
    """
    out = master.copy()
    for src, dst in zip(MASTER_KEYS, _JOIN_COLS_CANONICAL):
        out[dst] = strip_float_suffix(out[src]).astype("int64")
    return out


def prepare_supply_keys(supply: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of supply with the three join key columns normalised.
    Adds columns ``_jk_item``, ``_jk_model``, ``_jk_udidi`` as int64.
    """
    out = supply.copy()
    for src, dst in zip(SUPPLY_KEYS, _JOIN_COLS_CANONICAL):
        out[dst] = strip_float_suffix(out[src]).astype("int64")
    return out


def join_master_supply(
    master: pd.DataFrame,
    supply: pd.DataFrame,
    *,
    how: str = "inner",
) -> pd.DataFrame:
    """
    Perform the mandatory 3-key composite join between master and supply.

    Uses temporary canonical key columns to avoid column name collisions between
    the two datasets (master uses 'UDIDI일련번호'; supply uses 'UDI-DI 일련번호').

    Parameters
    ----------
    master:
        Output of :func:`prepare_master_keys`.
    supply:
        Output of :func:`prepare_supply_keys`.
    how:
        Join type ('inner', 'left', 'right').  Default 'inner'.

    Returns
    -------
    pd.DataFrame
        Joined DataFrame with supply rows on the left, master columns suffixed '_m'.
    """
    m = prepare_master_keys(master)
    s = prepare_supply_keys(supply)

    joined = s.merge(
        m,
        on=_JOIN_COLS_CANONICAL,
        how=how,
        suffixes=("", "_m"),
    )
    joined = joined.drop(columns=_JOIN_COLS_CANONICAL)
    return joined
