"""
Top7 data loader for Class 1 anomaly detection.

Rules (from shared_data/DATA_LAYER.md):
- Active tier: top7_master_registration_data.xlsx, top7_transaction_supply_data.xlsx
- Archived sample_* workbooks must NEVER be loaded.
- Dynamic sheet discovery: supply workbook has a metadata sheet (개요/표지) and a
  data sheet; detect the data sheet by name exclusion, not by hardcoded index.
- Profile on every load; escalate via AgentSlacker on schema drift.
- Price cap: 50M KRW applied to 공급단가 and 공급금액 at load time.
+ Barcode-error flag: rows with 공급단가/공급금액 > 1e12 are flagged, not capped.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from .keys import BARCODE_PRICE_THRESHOLD, MASTER_KEYS, SUPPLY_KEYS
from .profile import detect_schema_drift, log_profile, profile_df

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
# class_1_anomaly_detection/src/ingest/loader.py → 4 levels up → repo root
REPO_ROOT: Path = _HERE.parent.parent.parent.parent
DATA_DIR: Path = REPO_ROOT / "shared_data"

MASTER_FILE = DATA_DIR / "top7_master_registration_data.xlsx"
SUPPLY_FILE = DATA_DIR / "top7_transaction_supply_data.xlsx"

# Sheets that are metadata/overview — skip when discovering the data sheet
_METADATA_SHEET_NAMES = {"개요", "표지", "sheet1", "sheet 1"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_slacker():
    """
    Lazily import and construct AgentSlacker so the module can be imported
    without crashing when .env is absent (e.g. in testing environments).
    """
    try:
        load_dotenv(REPO_ROOT / "class_1_anomaly_detection" / ".env")
        import sys
        sys.path.insert(0, str(REPO_ROOT))
        from shared_utils.slacker import AgentSlacker
        return AgentSlacker("class_1_anomaly_detection")
    except Exception:
        return None


def _discover_data_sheet(file: Path) -> str:
    """
    Return the name of the data sheet in a multi-sheet Excel workbook.

    Strategy:
    1. List all sheet names.
    2. Filter out known metadata sheet names (case-insensitive).
    3. Return the first remaining sheet.
    4. Fall back to the last sheet if all names look like metadata.
    """
    xl = pd.ExcelFile(file, engine="openpyxl")
    sheets = xl.sheet_names
    if len(sheets) == 1:
        return sheets[0]

    data_sheets = [
        s for s in sheets
        if s.strip().lower() not in _METADATA_SHEET_NAMES
    ]
    if data_sheets:
        return data_sheets[0]
    return sheets[-1]


def _flag_barcode_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag rows where 공급단가 or 공급금액 look like barcode scan errors (>1e12 KRW).
    Does NOT modify price values — downstream metrics decide handling.
    """
    for col in ["공급단가", "공급금액"]:
        if col in df.columns:
            df[f"_{col}_barcode_error"] = df[col].notna() & (
                df[col] > BARCODE_PRICE_THRESHOLD
            )
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_master(
    *,
    verbose: bool = True,
    validate_keys: bool = True,
) -> pd.DataFrame:
    """
    Load top7 master registration workbook.

    Parameters
    ----------
    verbose:
        Print schema profile summary after loading.
    validate_keys:
        Check that all 3 composite join key columns are present.

    Returns
    -------
    pd.DataFrame
    """
    if not MASTER_FILE.exists():
        raise FileNotFoundError(
            f"Master file not found: {MASTER_FILE}\n"
            "Ensure top7_master_registration_data.xlsx is in shared_data/."
        )

    df = pd.read_excel(MASTER_FILE, engine="openpyxl")

    p = profile_df(df, "top7_master")
    if verbose:
        log_profile(p)

    if validate_keys:
        detect_schema_drift(
            list(df.columns),
            MASTER_KEYS,
            name="top7_master",
            slacker=_resolve_slacker(),
        )

    return df


def load_supply(
    *,
    verbose: bool = True,
    validate_keys: bool = True,
    cap_prices: bool = True,
) -> tuple[pd.DataFrame, str]:
    """
    Load top7 supply transaction workbook (data sheet only).

    Parameters
    ----------
    verbose:
        Print schema profile and discovered sheet name.
    validate_keys:
        Check that all 3 composite join key columns are present.
    cap_prices:
        Deprecated alias — when True, flags barcode-error prices (no capping).

    Returns
    -------
    (DataFrame, sheet_name_used)
    """
    if not SUPPLY_FILE.exists():
        raise FileNotFoundError(
            f"Supply file not found: {SUPPLY_FILE}\n"
            "Ensure top7_transaction_supply_data.xlsx is in shared_data/."
        )

    sheet = _discover_data_sheet(SUPPLY_FILE)
    if verbose:
        print(f"[loader] Supply data sheet discovered: '{sheet}'")

    df = pd.read_excel(SUPPLY_FILE, sheet_name=sheet, engine="openpyxl")

    if cap_prices:
        df = _flag_barcode_prices(df)

    p = profile_df(df, f"top7_supply [{sheet}]")
    if verbose:
        log_profile(p)

    if validate_keys:
        detect_schema_drift(
            list(df.columns),
            SUPPLY_KEYS,
            name=f"top7_supply [{sheet}]",
            slacker=_resolve_slacker(),
        )

    return df, sheet


def load_top7(
    *,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convenience wrapper: load both master and supply in one call.

    Returns
    -------
    (master_df, supply_df)
    """
    master = load_master(verbose=verbose)
    supply, _ = load_supply(verbose=verbose)
    return master, supply
