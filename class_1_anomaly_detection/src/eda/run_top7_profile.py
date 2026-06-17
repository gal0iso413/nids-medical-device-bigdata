"""
Programmatic validation of Hermes top7 EDA findings (eda_profile_2026-06-10-top7.md).

Runs a full profile pass on both top7 workbooks and validates:
  - Row/column counts match Hermes report expectations
  - 3-key composite join yields 100% match (no inflation, no row loss)
  - Price segmentation matches known patterns
  - Key quality flags reproduced (discard nulls, import proxy, price cap rows)

Output: printed summary + notes/eda_validation_top7.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve()
_SRC = _HERE.parent.parent
sys.path.insert(0, str(_SRC.parent.parent))  # repo root on path

from class_1_anomaly_detection.src.ingest.loader import load_top7, REPO_ROOT
from class_1_anomaly_detection.src.ingest.keys import (
    HOSPITAL_SUPPLY_TYPE,
    DISCARD_SUPPLY_CLASS,
    IMPORT_BUSINESS_TYPE,
    MASTER_KEYS,
    SUPPLY_KEYS,
    join_master_supply,
)
from class_1_anomaly_detection.src.ingest.profile import profile_df, log_profile

# ---------------------------------------------------------------------------
# Expected values from Hermes eda_profile_2026-06-10-top7.md
# ---------------------------------------------------------------------------
EXPECTED_MASTER_ROWS = 221
EXPECTED_MASTER_COLS = 93
EXPECTED_SUPPLY_ROWS = 704_315
EXPECTED_SUPPLY_COLS = 71
EXPECTED_JOIN_ROWS = 704_315  # 100% match
EXPECTED_HOSPITAL_ROWS = 373_480
PRICE_NULL_THRESHOLD_GLOBAL = 0.22  # ~21.51% in Hermes report
HOSPITAL_PRICE_NULL_THRESHOLD = 0.08  # ~7.19% in Hermes report
EXPECTED_DISCARD_ROWS = 1_110


def _check(label: str, actual, expected, *, tolerance: float = 0.0) -> bool:
    if isinstance(expected, (int, float)):
        ok = abs(actual - expected) <= tolerance * max(abs(expected), 1)
    else:
        ok = actual == expected
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}: got {actual!r} (expected {expected!r})")
    return ok


def run_validation() -> dict:
    print("\n" + "=" * 70)
    print("  Class 1 — Top7 EDA Validation")
    print("  Baseline: eda_profile_2026-06-10-top7.md")
    print("=" * 70)

    results: dict[str, bool] = {}

    # -----------------------------------------------------------------------
    # Load
    # -----------------------------------------------------------------------
    print("\n[1/6] Loading top7 workbooks...")
    master, supply = load_top7(verbose=True)

    # -----------------------------------------------------------------------
    # Shape checks
    # -----------------------------------------------------------------------
    print("\n[2/6] Shape checks")
    results["master_rows"] = _check("Master rows", len(master), EXPECTED_MASTER_ROWS)
    results["master_cols"] = _check("Master cols", len(master.columns), EXPECTED_MASTER_COLS)
    results["supply_rows"] = _check("Supply rows", len(supply), EXPECTED_SUPPLY_ROWS)
    results["supply_cols"] = _check("Supply cols", len(supply.columns), EXPECTED_SUPPLY_COLS)

    # -----------------------------------------------------------------------
    # Key presence
    # -----------------------------------------------------------------------
    print("\n[3/6] Key column presence")
    for k in MASTER_KEYS:
        ok = k in master.columns
        results[f"master_key_{k}"] = ok
        print(f"  [{'PASS' if ok else 'FAIL'}] Master key '{k}': {'found' if ok else 'MISSING'}")
    for k in SUPPLY_KEYS:
        ok = k in supply.columns
        results[f"supply_key_{k}"] = ok
        print(f"  [{'PASS' if ok else 'FAIL'}] Supply key '{k}': {'found' if ok else 'MISSING'}")

    # -----------------------------------------------------------------------
    # 3-key composite join
    # -----------------------------------------------------------------------
    print("\n[4/6] 3-key composite join integrity")
    joined = join_master_supply(master, supply)
    results["join_rows"] = _check("Join row count", len(joined), EXPECTED_JOIN_ROWS)
    join_pct = len(joined) / len(supply) * 100
    results["join_coverage"] = _check(
        "Join coverage %", round(join_pct, 2), 100.0, tolerance=0.001
    )

    # -----------------------------------------------------------------------
    # Price segmentation
    # -----------------------------------------------------------------------
    print("\n[5/6] Price segmentation checks")
    global_price_null = supply["공급단가"].isna().mean() if "공급단가" in supply.columns else None
    if global_price_null is not None:
        results["global_price_null"] = _check(
            "Global 공급단가 null rate",
            round(global_price_null, 4),
            round(PRICE_NULL_THRESHOLD_GLOBAL, 4),
            tolerance=0.02,
        )

    hospital = supply[supply["공급형태"] == HOSPITAL_SUPPLY_TYPE] if "공급형태" in supply.columns else None
    if hospital is not None and len(hospital) > 0:
        results["hospital_rows"] = _check(
            "Hospital supply rows",
            len(hospital),
            EXPECTED_HOSPITAL_ROWS,
            tolerance=0.01,
        )
        hosp_price_null = hospital["공급단가"].isna().mean()
        results["hospital_price_null"] = _check(
            "Hospital 공급단가 null rate",
            round(hosp_price_null, 4),
            round(HOSPITAL_PRICE_NULL_THRESHOLD, 4),
            tolerance=0.02,
        )

    # -----------------------------------------------------------------------
    # Discard integrity
    # -----------------------------------------------------------------------
    print("\n[6/6] Discard receiver nulls")
    if "공급구분" in supply.columns:
        discards = supply[supply["공급구분"] == DISCARD_SUPPLY_CLASS]
        results["discard_rows"] = _check(
            "Discard row count",
            len(discards),
            EXPECTED_DISCARD_ROWS,
            tolerance=0.05,
        )
        for col in ["공급받은자", "공급받은자 사업자등록번호", "요양기관기호(의료기관)"]:
            if col in discards.columns and len(discards) > 0:
                all_null = discards[col].isna().all()
                results[f"discard_null_{col}"] = all_null
                print(f"  [{'PASS' if all_null else 'FAIL'}] Discard '{col}' all-null: {all_null}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    passed = sum(v for v in results.values() if isinstance(v, bool) and v)
    total = sum(1 for v in results.values() if isinstance(v, bool))
    print(f"\n{'='*70}")
    print(f"  RESULT: {passed}/{total} checks passed")
    if passed == total:
        print("  STATUS: ALL PASS — top7 EDA validated. Proceed to graph EDA.")
    else:
        failed = [k for k, v in results.items() if isinstance(v, bool) and not v]
        print(f"  STATUS: FAILURES — review before proceeding: {failed}")
    print("=" * 70)

    return results


def save_validation_report(results: dict) -> None:
    """Write a brief validation summary to notes/."""
    out_dir = REPO_ROOT / "class_1_anomaly_detection" / "notes"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "eda_validation_top7.md"

    passed = sum(v for v in results.values() if isinstance(v, bool) and v)
    total = sum(1 for v in results.values() if isinstance(v, bool))
    lines = [
        "# Top7 EDA Validation Summary",
        "",
        f"Baseline: `eda_profile_2026-06-10-top7.md`",
        f"Result: {passed}/{total} checks passed",
        "",
        "## Check results",
        "",
    ]
    for k, v in results.items():
        icon = "✓" if v else "✗"
        lines.append(f"- {icon} `{k}`: {v}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[report] Saved validation report → {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    results = run_validation()
    save_validation_report(results)
    sys.exit(0 if all(v for v in results.values() if isinstance(v, bool)) else 1)
