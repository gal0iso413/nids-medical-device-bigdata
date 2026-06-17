"""
Runtime schema profiler for top7 workbooks.

Called on every load. On column drift, posts a roadblock escalation via
AgentSlacker and raises RuntimeError to prevent silent downstream corruption.
"""
from __future__ import annotations

import sys
from typing import Any

import pandas as pd


def profile_df(df: pd.DataFrame, name: str) -> dict[str, Any]:
    """
    Compute a lightweight schema profile for a DataFrame.

    Returns a dict with:
      - shape: (rows, cols)
      - dtypes: column -> dtype string
      - null_rates: column -> fraction null (0.0–1.0)
      - high_null: columns with null_rate > 0.50
      - moderate_null: columns with null_rate 0.20–0.50
      - cardinality: column -> unique count (capped at 500 for large DFs)
    """
    rows, cols = df.shape
    null_rates: dict[str, float] = {}
    cardinality: dict[str, int] = {}

    for col in df.columns:
        nr = float(df[col].isna().mean())
        null_rates[col] = round(nr, 4)
        if rows <= 500_000:
            cardinality[col] = int(df[col].nunique(dropna=False))

    high_null = [c for c, r in null_rates.items() if r > 0.50]
    moderate_null = [c for c, r in null_rates.items() if 0.20 <= r <= 0.50]

    return {
        "name": name,
        "shape": (rows, cols),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "null_rates": null_rates,
        "high_null": high_null,
        "moderate_null": moderate_null,
        "cardinality": cardinality,
    }


def log_profile(profile: dict[str, Any], *, file=None) -> None:
    """Print a formatted summary of a profile dict."""
    f = file or sys.stdout
    name = profile["name"]
    rows, cols = profile["shape"]
    print(f"\n{'='*60}", file=f)
    print(f"  Profile: {name}", file=f)
    print(f"  Shape  : {rows:,} rows × {cols} columns", file=f)
    print(f"{'='*60}", file=f)

    high = profile["high_null"]
    if high:
        print(f"  HIGH NULL (>50%) — {len(high)} cols:", file=f)
        for c in high[:10]:
            r = profile["null_rates"][c]
            print(f"    {c}: {r:.1%}", file=f)
        if len(high) > 10:
            print(f"    ... and {len(high)-10} more", file=f)

    mod = profile["moderate_null"]
    if mod:
        print(f"  MODERATE NULL (20–50%) — {len(mod)} cols:", file=f)
        for c in mod:
            r = profile["null_rates"][c]
            print(f"    {c}: {r:.1%}", file=f)

    card = profile.get("cardinality", {})
    if card:
        low_card = [(c, v) for c, v in card.items() if v <= 20 and v > 1][:8]
        if low_card:
            print(f"  LOW CARDINALITY (≤20 unique):", file=f)
            for c, v in low_card:
                print(f"    {c}: {v} unique", file=f)


def detect_schema_drift(
    loaded_cols: list[str],
    required_cols: list[str],
    *,
    name: str = "dataframe",
    slacker=None,
    strict: bool = True,
    baseline_cols: list[str] | None = None,
) -> None:
    """
    Validate that **required** columns (e.g. join keys) are present after load.

    Per DATA_LAYER.md, workbooks are profiled dynamically — extra columns beyond
    a required subset are normal and must not be treated as drift.  Only missing
    required columns escalate.

    If ``baseline_cols`` is supplied (full Hermes/profile snapshot), log a
    non-blocking warning when loaded columns diverge from that baseline.
    """
    loaded_set = set(loaded_cols)
    missing = sorted(set(required_cols) - loaded_set)

    if baseline_cols is not None:
        baseline_set = set(baseline_cols)
        extra = sorted(loaded_set - baseline_set)
        missing_baseline = sorted(baseline_set - loaded_set)
        if extra or missing_baseline:
            print(
                f"[profile] Schema drift in '{name}' vs baseline: "
                f"+{len(extra)} new, -{len(missing_baseline)} removed. "
                "Re-profile recommended.",
                file=sys.stderr,
            )

    if missing:
        msg = (
            f"Schema drift in '{name}': {len(missing)} required columns are missing — "
            f"{missing}. Cannot proceed without PM directive."
        )
        if slacker is not None:
            slacker.escalate_roadblock(
                issue_title=f"Schema drift: {name}",
                context_dump=(
                    f"Missing required columns: {missing}\n"
                    f"Loaded column count: {len(loaded_cols)}"
                ),
                agent_counter_argument=(
                    "top7 workbook schema has changed since Hermes profiling on 2026-06-10. "
                    "PM must confirm new column mappings before ingestion proceeds."
                ),
                broadcast_global=True,
            )
        if strict:
            raise RuntimeError(msg)
        print(f"[profile] WARNING: {msg}", file=sys.stderr)
