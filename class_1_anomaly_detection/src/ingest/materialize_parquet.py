"""
Materialize Excel workbooks into agent-local Parquet partitions.

UI and training should read Parquet after the first successful materialize
(never open Excel on every run).

Onsite (first visit) — keep it small:
  python -m class_1_anomaly_detection.src.ingest.materialize_parquet --force --last-n-months 4

Full history (later visits / overnight):
  python -m class_1_anomaly_detection.src.ingest.materialize_parquet --force

Point at real files without copying into shared_data/:
  set NIDS_MASTER_XLSX=D:\\data\\master.xlsx
  set NIDS_SUPPLY_XLSX=D:\\data\\supply.xlsx
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_1_anomaly_detection.src.ingest.keys import COL_BASE_MONTH
from class_1_anomaly_detection.src.ingest.loader import (
    MASTER_FILE,
    SUPPLY_FILE,
    load_master,
    load_supply,
)

PARQUET_ROOT = _REPO_ROOT / "class_1_anomaly_detection" / "data" / "parquet"
MASTER_PARQUET = PARQUET_ROOT / "master.parquet"
SUPPLY_DIR = PARQUET_ROOT / "supply"
MANIFEST_PATH = PARQUET_ROOT / "manifest.json"


def parquet_ready() -> bool:
    return MASTER_PARQUET.exists() and SUPPLY_DIR.exists() and any(SUPPLY_DIR.glob("*.parquet"))


def _filter_last_n_months(supply: pd.DataFrame, last_n_months: int) -> tuple[pd.DataFrame, list[str]]:
    if COL_BASE_MONTH not in supply.columns or last_n_months <= 0:
        return supply, []
    months = sorted(
        m
        for m in supply[COL_BASE_MONTH].astype(str).str.strip().unique()
        if m and m.lower() not in {"nan", "none"}
    )
    keep = months[-last_n_months:]
    mask = supply[COL_BASE_MONTH].astype(str).str.strip().isin(keep)
    return supply.loc[mask].copy(), keep


def materialize(
    *,
    force: bool = False,
    verbose: bool = True,
    last_n_months: int | None = None,
) -> dict:
    PARQUET_ROOT.mkdir(parents=True, exist_ok=True)
    SUPPLY_DIR.mkdir(parents=True, exist_ok=True)

    if parquet_ready() and not force:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
        if verbose:
            print(f"[parquet] Already materialized at {PARQUET_ROOT} — use --force to rebuild.")
        return manifest

    t0 = time.perf_counter()
    if verbose:
        print("[parquet] Loading Excel (one-time materialize)…")
        print(f"[parquet] Master: {MASTER_FILE}")
        print(f"[parquet] Supply: {SUPPLY_FILE}")

    master = load_master(verbose=verbose)
    supply, sheet = load_supply(verbose=verbose)

    kept_months: list[str] = []
    if last_n_months is not None and last_n_months > 0:
        supply, kept_months = _filter_last_n_months(supply, last_n_months)
        if verbose:
            print(
                f"[parquet] Onsite filter: last {last_n_months} months → "
                f"{kept_months[0] if kept_months else '?'} .. "
                f"{kept_months[-1] if kept_months else '?'} "
                f"({len(supply):,} rows)"
            )

    master.to_parquet(MASTER_PARQUET, index=False)

    for old in SUPPLY_DIR.glob("*.parquet"):
        old.unlink()

    months: list[str] = []
    if COL_BASE_MONTH in supply.columns:
        supply = supply.copy()
        supply["_month"] = supply[COL_BASE_MONTH].astype(str).str.strip()
        for month, part in supply.groupby("_month", sort=True):
            m = str(month)
            if not m or m.lower() in {"nan", "none"}:
                continue
            months.append(m)
            out = part.drop(columns=["_month"])
            out.to_parquet(SUPPLY_DIR / f"month_{m}.parquet", index=False)
    else:
        supply.to_parquet(SUPPLY_DIR / "month_all.parquet", index=False)
        months = ["all"]

    elapsed = round(time.perf_counter() - t0, 2)
    manifest = {
        "master_rows": int(len(master)),
        "supply_rows": int(len(supply)),
        "supply_sheet": sheet,
        "months": months,
        "last_n_months_filter": last_n_months,
        "master_source": str(MASTER_FILE),
        "supply_source": str(SUPPLY_FILE),
        "elapsed_sec": elapsed,
        "parquet_root": str(PARQUET_ROOT.relative_to(_REPO_ROOT)).replace("\\", "/"),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    if verbose:
        print(f"[parquet] Wrote master={len(master):,} rows; supply months={len(months)}; {elapsed}s")
        print(f"[parquet] Root: {PARQUET_ROOT}")
    return manifest


def load_master_parquet() -> pd.DataFrame:
    if not MASTER_PARQUET.exists():
        raise FileNotFoundError(
            f"Missing {MASTER_PARQUET} — run materialize_parquet first."
        )
    return pd.read_parquet(MASTER_PARQUET)


def load_supply_parquet(
    *,
    months: list[str] | None = None,
) -> pd.DataFrame:
    if not SUPPLY_DIR.exists():
        raise FileNotFoundError(
            f"Missing {SUPPLY_DIR} — run materialize_parquet first."
        )
    files = sorted(SUPPLY_DIR.glob("month_*.parquet"))
    if not files:
        raise FileNotFoundError(f"No supply partitions under {SUPPLY_DIR}")

    if months is not None:
        wanted = {f"month_{m}.parquet" for m in months}
        files = [p for p in files if p.name in wanted]
        if not files:
            raise FileNotFoundError(f"No partitions for months={months}")

    frames = [pd.read_parquet(p) for p in files]
    return pd.concat(frames, ignore_index=True)


def load_top7_prefer_parquet(
    *,
    verbose: bool = True,
    prefer_parquet: bool = True,
    materialize_if_missing: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Preferred runtime loader: Parquet if present; optionally materialize once."""
    if prefer_parquet and parquet_ready():
        if verbose:
            print("[loader] Reading Parquet working store (Excel skipped).")
        return load_master_parquet(), load_supply_parquet()

    if prefer_parquet and materialize_if_missing:
        materialize(force=False, verbose=verbose)
        return load_master_parquet(), load_supply_parquet()

    from class_1_anomaly_detection.src.ingest.loader import load_top7

    return load_top7(verbose=verbose)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize Excel → Parquet")
    parser.add_argument("--force", action="store_true", help="Rebuild even if present")
    parser.add_argument(
        "--last-n-months",
        type=int,
        default=None,
        help="Onsite speed mode: keep only the latest N supply months (e.g. 4).",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    materialize(
        force=args.force,
        verbose=not args.quiet,
        last_n_months=args.last_n_months,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
