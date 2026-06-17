"""Runtime schema profiler — Class 3 Impact Evaluation."""
from __future__ import annotations

import sys
from typing import Any

import pandas as pd


def profile_df(df: pd.DataFrame, name: str) -> dict[str, Any]:
    rows, cols = df.shape
    null_rates: dict[str, float] = {}
    cardinality: dict[str, int] = {}
    for col in df.columns:
        null_rates[col] = round(float(df[col].isna().mean()), 4)
        if rows <= 500_000:
            cardinality[col] = int(df[col].nunique(dropna=False))
    return {
        "name": name,
        "shape": (rows, cols),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "null_rates": null_rates,
        "high_null": [c for c, r in null_rates.items() if r > 0.50],
        "moderate_null": [c for c, r in null_rates.items() if 0.20 <= r <= 0.50],
        "cardinality": cardinality,
    }


def log_profile(profile: dict[str, Any], *, file=None) -> None:
    f = file or sys.stdout
    rows, cols = profile["shape"]
    print(f"\n{'='*60}", file=f)
    print(f"  Profile: {profile['name']}", file=f)
    print(f"  Shape  : {rows:,} rows × {cols} columns", file=f)
    print(f"{'='*60}", file=f)
    high = profile["high_null"]
    if high:
        print(f"  HIGH NULL (>50%) — {len(high)} cols:", file=f)
        for c in high[:8]:
            print(f"    {c}: {profile['null_rates'][c]:.1%}", file=f)
        if len(high) > 8:
            print(f"    ... and {len(high)-8} more", file=f)
    mod = profile["moderate_null"]
    if mod:
        print(f"  MODERATE NULL (20–50%) — {len(mod)} cols:", file=f)
        for c in mod:
            print(f"    {c}: {profile['null_rates'][c]:.1%}", file=f)


def detect_schema_drift(
    loaded_cols: list[str],
    required_cols: list[str],
    *,
    name: str = "dataframe",
    slacker=None,
    strict: bool = True,
    baseline_cols: list[str] | None = None,
) -> None:
    """Validate required columns only; extra columns are not drift (see DATA_LAYER.md)."""
    loaded_set = set(loaded_cols)
    missing = sorted(set(required_cols) - loaded_set)

    if baseline_cols is not None:
        baseline_set = set(baseline_cols)
        extra = sorted(loaded_set - baseline_set)
        missing_baseline = sorted(baseline_set - loaded_set)
        if extra or missing_baseline:
            print(
                f"[profile] Schema drift '{name}' vs baseline: "
                f"+{len(extra)} new, -{len(missing_baseline)} removed.",
                file=sys.stderr,
            )

    if missing:
        msg = f"Schema drift '{name}': missing required {missing}"
        if slacker is not None:
            slacker.escalate_roadblock(
                issue_title=f"Schema drift: {name}",
                context_dump=f"Missing required: {missing}",
                agent_counter_argument=(
                    "top7 workbook schema changed since Hermes profiling 2026-06-10. "
                    "PM must confirm new column mappings."
                ),
                broadcast_global=True,
            )
        if strict:
            raise RuntimeError(msg)
        print(f"[profile] WARNING: {msg}", file=sys.stderr)
