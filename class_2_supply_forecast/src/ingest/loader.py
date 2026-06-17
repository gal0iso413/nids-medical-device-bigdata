"""
Top7 data loader — Class 2 Supply Forecast & Early Warning.
Same top7 files as Class 1; agent name and .env path differ.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from .keys import PRICE_CAP_KRW, MASTER_KEYS, SUPPLY_KEYS
from .profile import detect_schema_drift, log_profile, profile_df

_HERE = Path(__file__).resolve()
REPO_ROOT: Path = _HERE.parent.parent.parent.parent
DATA_DIR: Path = REPO_ROOT / "shared_data"

MASTER_FILE = DATA_DIR / "top7_master_registration_data.xlsx"
SUPPLY_FILE = DATA_DIR / "top7_transaction_supply_data.xlsx"

_METADATA_SHEET_NAMES = {"개요", "표지", "sheet1", "sheet 1"}


def _resolve_slacker():
    try:
        load_dotenv(REPO_ROOT / "class_2_supply_forecast" / ".env")
        import sys
        sys.path.insert(0, str(REPO_ROOT))
        from shared_utils.slacker import AgentSlacker
        return AgentSlacker("class_2_supply_forecast")
    except Exception:
        return None


def _discover_data_sheet(file: Path) -> str:
    xl = pd.ExcelFile(file, engine="openpyxl")
    sheets = xl.sheet_names
    if len(sheets) == 1:
        return sheets[0]
    data_sheets = [s for s in sheets if s.strip().lower() not in _METADATA_SHEET_NAMES]
    return data_sheets[0] if data_sheets else sheets[-1]


def _cap_price_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in [c for c in ["공급단가", "공급금액"] if c in df.columns]:
        mask = df[col].notna() & (df[col] > PRICE_CAP_KRW)
        if mask.any():
            df[f"_{col}_capped"] = mask
            df[col] = df[col].clip(upper=PRICE_CAP_KRW)
    return df


def load_master(*, verbose: bool = True, validate_keys: bool = True) -> pd.DataFrame:
    if not MASTER_FILE.exists():
        raise FileNotFoundError(f"Master file not found: {MASTER_FILE}")
    df = pd.read_excel(MASTER_FILE, engine="openpyxl")
    p = profile_df(df, "top7_master [class2]")
    if verbose:
        log_profile(p)
    if validate_keys:
        detect_schema_drift(list(df.columns), MASTER_KEYS, name="top7_master", slacker=_resolve_slacker())
    return df


def load_supply(
    *, verbose: bool = True, validate_keys: bool = True, cap_prices: bool = True
) -> tuple[pd.DataFrame, str]:
    if not SUPPLY_FILE.exists():
        raise FileNotFoundError(f"Supply file not found: {SUPPLY_FILE}")
    sheet = _discover_data_sheet(SUPPLY_FILE)
    if verbose:
        print(f"[loader] Supply data sheet discovered: '{sheet}'")
    df = pd.read_excel(SUPPLY_FILE, sheet_name=sheet, engine="openpyxl")
    if cap_prices:
        df = _cap_price_columns(df)
    p = profile_df(df, f"top7_supply [class2] [{sheet}]")
    if verbose:
        log_profile(p)
    if validate_keys:
        detect_schema_drift(list(df.columns), SUPPLY_KEYS, name=f"top7_supply [{sheet}]", slacker=_resolve_slacker())
    return df, sheet


def load_top7(*, verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    master = load_master(verbose=verbose)
    supply, _ = load_supply(verbose=verbose)
    return master, supply
