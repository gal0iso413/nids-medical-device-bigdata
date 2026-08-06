"""
Data loader for Class 1 anomaly detection.

Lab (top7): single master + single supply workbook under shared_data/.
Onsite (production): master may have multiple sheets; supply is often **many
workbooks** (Visit 1: 12 files / ~12M rows for 4 months) — set NIDS_SUPPLY_DIR.

Env overrides:
  NIDS_MASTER_XLSX   absolute path to master workbook
  NIDS_SUPPLY_XLSX   absolute path to ONE supply workbook (lab / smoke)
  NIDS_SUPPLY_DIR    directory of many supply *.xlsx / *.xlsm (onsite)

Rules (shared_data/DATA_LAYER.md):
- Archived sample_* workbooks must NEVER be loaded.
- Skip metadata sheets (개요/표지); merge remaining data sheets.
- Profile on load; escalate via AgentSlacker on schema drift.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from .keys import BARCODE_PRICE_THRESHOLD, MASTER_KEYS, SUPPLY_KEYS
from .profile import detect_schema_drift, log_profile, profile_df

_HERE = Path(__file__).resolve()
REPO_ROOT: Path = _HERE.parent.parent.parent.parent
DATA_DIR: Path = REPO_ROOT / "shared_data"

MASTER_FILE = Path(
    os.environ.get("NIDS_MASTER_XLSX", str(DATA_DIR / "top7_master_registration_data.xlsx"))
)
SUPPLY_FILE = Path(
    os.environ.get("NIDS_SUPPLY_XLSX", str(DATA_DIR / "top7_transaction_supply_data.xlsx"))
)
# Onsite: folder of many supply workbooks (takes precedence over NIDS_SUPPLY_XLSX when set)
SUPPLY_DIR = (
    Path(os.environ["NIDS_SUPPLY_DIR"]) if os.environ.get("NIDS_SUPPLY_DIR") else None
)

_METADATA_SHEET_NAMES = {"개요", "표지", "sheet1", "sheet 1"}
_SUPPLY_GLOBS = ("*.xlsx", "*.xlsm", "*.XLSX", "*.XLSM")


def _resolve_slacker():
    try:
        load_dotenv(REPO_ROOT / "class_1_anomaly_detection" / ".env")
        import sys

        sys.path.insert(0, str(REPO_ROOT))
        from shared_utils.slacker import AgentSlacker

        return AgentSlacker("class_1_anomaly_detection")
    except Exception:
        return None


def _is_metadata_sheet(name: str) -> bool:
    return name.strip().lower() in _METADATA_SHEET_NAMES


def _list_data_sheets(file: Path) -> list[str]:
    xl = pd.ExcelFile(file, engine="openpyxl")
    sheets = xl.sheet_names
    data = [s for s in sheets if not _is_metadata_sheet(s)]
    if data:
        return data
    return [sheets[-1]] if sheets else []


def _discover_data_sheet(file: Path) -> str:
    """Backward-compatible: first non-metadata sheet."""
    sheets = _list_data_sheets(file)
    return sheets[0]


def _normalize_col_label(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    # pandas may emit Unnamed: 0 style placeholders
    if text.lower().startswith("unnamed"):
        return ""
    return text


def _header_overlap_ratio(candidate: list[object], reference: list[object]) -> float:
    """Fraction of reference labels found in candidate (order-independent)."""
    ref = {_normalize_col_label(c) for c in reference}
    ref.discard("")
    if not ref:
        return 0.0
    got = {_normalize_col_label(c) for c in candidate}
    got.discard("")
    return len(ref & got) / len(ref)


def _sheet_has_header_row(
    file: Path,
    sheet: str,
    reference_columns: list[object],
    *,
    min_overlap: float = 0.5,
) -> bool:
    """
    Decide whether ``sheet`` starts with a header row.

    Uses overlap between the sheet's first row (as values) / inferred column
    names and the reference columns from the first headed sheet.
    """
    preview = pd.read_excel(
        file,
        sheet_name=sheet,
        header=None,
        nrows=2,
        engine="openpyxl",
    )
    if preview.empty:
        return False

    first_row = preview.iloc[0].tolist()
    # Case A: first row values == header labels (typical "header on this sheet")
    if _header_overlap_ratio(first_row, reference_columns) >= min_overlap:
        return True

    # Case B: read with header=0; column Index matches reference
    headed = pd.read_excel(file, sheet_name=sheet, header=0, nrows=1, engine="openpyxl")
    if _header_overlap_ratio(list(headed.columns), reference_columns) >= min_overlap:
        return True

    return False


def _align_to_reference_columns(
    df: pd.DataFrame,
    reference_columns: list[object],
) -> pd.DataFrame:
    """Reindex / rename columns to the reference header list when possible."""
    if list(df.columns) == list(reference_columns):
        return df

    labels = [_normalize_col_label(c) for c in df.columns]
    anonymous = all(
        (lab == "" or str(col).isdigit() or isinstance(col, (int, float)))
        for col, lab in zip(df.columns, labels)
    )

    # Headerless continuation sheets: RangeIndex / blank names → positional map
    if anonymous and len(df.columns) == len(reference_columns):
        out = df.copy()
        out.columns = list(reference_columns)
        return out

    # Named header sheet (possibly reordered / subset)
    ref_by_norm = {_normalize_col_label(c): c for c in reference_columns}
    rename_map: dict[object, object] = {}
    for col in df.columns:
        key = _normalize_col_label(col)
        if key and key in ref_by_norm:
            rename_map[col] = ref_by_norm[key]
    out = df.rename(columns=rename_map)
    return out.reindex(columns=list(reference_columns))


def _read_workbook_all_data_sheets(
    file: Path,
    *,
    verbose: bool = False,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Read and concat all non-metadata sheets in one workbook.

    Header modes (auto-detected per sheet after the first headed sheet):
    - Every sheet has a header row (lab / some exports)
    - Only the first data sheet has headers; later sheets are data-only
      (common when Excel splits ~1M rows across sheets)
    """
    sheets = _list_data_sheets(file)
    if not sheets:
        return pd.DataFrame(), sheets

    frames: list[pd.DataFrame] = []
    reference_columns: list[object] | None = None
    header_modes: list[str] = []

    for sheet in sheets:
        if reference_columns is None:
            part = pd.read_excel(file, sheet_name=sheet, header=0, engine="openpyxl")
            if part is None or part.empty:
                if verbose:
                    print(f"  [loader] {file.name} / '{sheet}': empty — skip")
                continue
            reference_columns = list(part.columns)
            header_modes.append(f"{sheet}=header")
        else:
            has_header = _sheet_has_header_row(file, sheet, reference_columns)
            if has_header:
                part = pd.read_excel(file, sheet_name=sheet, header=0, engine="openpyxl")
                header_modes.append(f"{sheet}=header")
            else:
                part = pd.read_excel(file, sheet_name=sheet, header=None, engine="openpyxl")
                header_modes.append(f"{sheet}=no_header")
            if part is None or part.empty:
                if verbose:
                    print(f"  [loader] {file.name} / '{sheet}': empty — skip")
                continue
            part = _align_to_reference_columns(part, reference_columns)

        frames.append(part)
        if verbose:
            mode = header_modes[-1]
            print(f"  [loader] {file.name} / '{sheet}': {len(part):,} rows ({mode})")

    if not frames:
        return pd.DataFrame(), sheets

    if verbose and len(header_modes) > 1:
        print(f"  [loader] {file.name} header modes: {', '.join(header_modes)}")

    return pd.concat(frames, ignore_index=True), sheets


def _flag_barcode_prices(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["공급단가", "공급금액"]:
        if col in df.columns:
            df[f"_{col}_barcode_error"] = df[col].notna() & (
                df[col] > BARCODE_PRICE_THRESHOLD
            )
    return df


def _list_supply_workbooks(directory: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in _SUPPLY_GLOBS:
        files.extend(directory.glob(pattern))
    # de-dupe case variants on Windows
    uniq: dict[str, Path] = {}
    for p in files:
        if p.name.startswith("~$"):
            continue
        uniq[p.name.lower()] = p
    return sorted(uniq.values(), key=lambda p: p.name.lower())


def load_master(
    *,
    verbose: bool = True,
    validate_keys: bool = True,
) -> pd.DataFrame:
    """
    Load master registration workbook.

    Onsite: merges all non-metadata sheets (Visit 1: 3 sheets in one file).
    """
    if not MASTER_FILE.exists():
        raise FileNotFoundError(
            f"Master file not found: {MASTER_FILE}\n"
            "Set NIDS_MASTER_XLSX or place top7_master_registration_data.xlsx in shared_data/."
        )

    df, sheets = _read_workbook_all_data_sheets(MASTER_FILE, verbose=verbose)
    if verbose:
        print(f"[loader] Master sheets merged: {sheets} → {len(df):,} rows")

    p = profile_df(df, "master")
    if verbose:
        log_profile(p)

    if validate_keys:
        detect_schema_drift(
            list(df.columns),
            MASTER_KEYS,
            name="master",
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
    Load supply transaction data.

    Priority:
    1. NIDS_SUPPLY_DIR — all *.xlsx in folder (onsite multi-workbook)
    2. NIDS_SUPPLY_XLSX / default single top7 file

    Each workbook: all non-metadata sheets are merged (Visit 1 pattern).
    """
    frames: list[pd.DataFrame] = []
    sources: list[str] = []

    if SUPPLY_DIR is not None:
        if not SUPPLY_DIR.is_dir():
            raise FileNotFoundError(f"NIDS_SUPPLY_DIR is not a directory: {SUPPLY_DIR}")
        workbooks = _list_supply_workbooks(SUPPLY_DIR)
        if not workbooks:
            raise FileNotFoundError(
                f"No .xlsx/.xlsm files under NIDS_SUPPLY_DIR={SUPPLY_DIR}"
            )
        if verbose:
            print(f"[loader] Supply directory: {SUPPLY_DIR} ({len(workbooks)} workbooks)")
        for wb in workbooks:
            part, sheets = _read_workbook_all_data_sheets(wb, verbose=verbose)
            if part.empty:
                continue
            frames.append(part)
            sources.append(f"{wb.name}:{','.join(sheets)}")
    else:
        if not SUPPLY_FILE.exists():
            raise FileNotFoundError(
                f"Supply file not found: {SUPPLY_FILE}\n"
                "Set NIDS_SUPPLY_DIR (multi-file onsite) or NIDS_SUPPLY_XLSX / shared_data top7 file."
            )
        if verbose:
            print(f"[loader] Supply single workbook: {SUPPLY_FILE}")
        part, sheets = _read_workbook_all_data_sheets(SUPPLY_FILE, verbose=verbose)
        frames.append(part)
        sources.append(f"{SUPPLY_FILE.name}:{','.join(sheets)}")

    if not frames:
        raise ValueError("No supply rows loaded from any workbook/sheet.")

    df = pd.concat(frames, ignore_index=True)
    source_label = f"merged[{len(sources)} sources]"

    if cap_prices:
        df = _flag_barcode_prices(df)

    p = profile_df(df, f"supply [{source_label}]")
    if verbose:
        log_profile(p)
        print(f"[loader] Supply total rows: {len(df):,}")

    if validate_keys:
        detect_schema_drift(
            list(df.columns),
            SUPPLY_KEYS,
            name=f"supply [{source_label}]",
            slacker=_resolve_slacker(),
        )

    return df, source_label


def load_top7(
    *,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    master = load_master(verbose=verbose)
    supply, _ = load_supply(verbose=verbose)
    return master, supply
