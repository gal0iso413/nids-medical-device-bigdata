"""
Production GAD-NR train-on-past / score-display-anchors pipeline.

Default production model is GAD-NR. Train on the earliest ``train_ratio`` of
available anchors (or ``--train-cutoff YYYYMM``), then score every display
anchor with the frozen weights when possible; otherwise fit per display anchor
and record the train set in the manifest.

Also supports ``--compare-others`` to run additional PyGOD models for confirmation
(does not change the production default).

Run from repo root:
  python -m class_1_anomaly_detection.src.experiments.run_gadnr_production --all-anchors
  python -m class_1_anomaly_detection.src.experiments.run_gadnr_production --anchor-month 202605
  python -m class_1_anomaly_detection.src.experiments.run_gadnr_production --all-anchors --compare-others
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_1_anomaly_detection.src.experiments.pygod_common import (
    DEFAULT_CONTAMINATION,
    ML_OUTPUT_DIR,
    apply_pygod_gadnr_patch,
    list_available_anchor_months,
    list_compare_ready_anchor_months,
    load_baseline_tables,
    load_pyg_data,
    normalize_anchor_month,
    save_model_scores,
    scores_to_frame,
    write_json,
)
from class_1_anomaly_detection.src.experiments.run_pygod_compare import (
    DEFAULT_EPOCH,
    DEFAULT_HID_DIM,
    _build_model,
    _require_pygod,
)

PRODUCTION_SLUG = "gadnr"
COMPARE_SLUGS = ("dominant", "anomalydae", "ocgnn")


def _resolve_train_display_split(
    anchors: list[str],
    *,
    train_cutoff: str | None,
    train_ratio: float,
) -> tuple[list[str], list[str]]:
    if not anchors:
        return [], []
    if train_cutoff:
        cut = normalize_anchor_month(train_cutoff)
        train = [a for a in anchors if a <= cut]
        if not train:
            train = anchors[:1]
        display = list(anchors)
        return train, display
    n_train = max(1, int(len(anchors) * train_ratio))
    n_train = min(n_train, len(anchors))
    train = anchors[:n_train]
    display = list(anchors)
    return train, display


def _fit_gadnr(data, *, epoch: int, hid_dim: int, gpu: int, verbose: int):
    apply_pygod_gadnr_patch()
    model = _build_model(PRODUCTION_SLUG, epoch=epoch, hid_dim=hid_dim, verbose=verbose)
    # PyGOD detectors accept gpu in constructor; rebuild if needed
    from pygod.detector import GADNR

    model = GADNR(
        hid_dim=hid_dim,
        num_layers=1,
        lr=0.01,
        epoch=epoch,
        gpu=gpu,
        verbose=verbose,
        contamination=DEFAULT_CONTAMINATION,
    )
    t0 = time.perf_counter()
    model.fit(data)
    elapsed = round(time.perf_counter() - t0, 2)
    scores = np.asarray(model.decision_score_, dtype=np.float64)
    # PyGOD detectors expose singular ``label_`` (not sklearn-style ``labels_``).
    labels = np.asarray(model.label_, dtype=np.int64)
    return scores, labels, elapsed


def _score_anchor(
    anchor: str,
    *,
    epoch: int,
    hid_dim: int,
    gpu: int,
    verbose: bool,
) -> dict[str, Any]:
    data, entity_ids = load_pyg_data(anchor)
    scores, labels, elapsed = _fit_gadnr(
        data, epoch=epoch, hid_dim=hid_dim, gpu=gpu, verbose=int(verbose)
    )
    baselines = load_baseline_tables(anchor)
    df = scores_to_frame(entity_ids, scores, labels, PRODUCTION_SLUG, baselines)
    path = save_model_scores(df, PRODUCTION_SLUG, anchor_month=anchor)
    return {
        "anchor_month": anchor,
        "model": PRODUCTION_SLUG,
        "n_entities": len(entity_ids),
        "elapsed_sec": elapsed,
        "scores_path": str(path),
    }


def run_production(
    *,
    anchors: list[str] | None = None,
    train_cutoff: str | None = None,
    train_ratio: float = 0.5,
    epoch: int = DEFAULT_EPOCH,
    hid_dim: int = DEFAULT_HID_DIM,
    gpu: int = -1,
    compare_others: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    _require_pygod()
    ready = anchors or list_compare_ready_anchor_months()
    if not ready:
        discovered = list_available_anchor_months()
        raise FileNotFoundError(
            "No compare-ready anchors (need PyG artifacts). "
            f"Discovered rolling anchors: {discovered}"
        )

    train_anchors, display_anchors = _resolve_train_display_split(
        ready, train_cutoff=train_cutoff, train_ratio=train_ratio
    )
    if verbose:
        print("=" * 70)
        print("  GAD-NR production train / display")
        print("=" * 70)
        print(f"  Train anchors  : {train_anchors}")
        print(f"  Display anchors: {display_anchors}")
        print(f"  GPU            : {gpu}")

    # Fit on each train anchor (establishes production scores + documents train set).
    # For v1 each display anchor is scored independently with the same hyperparameters
    # (frozen architecture); train set is recorded for evaluation/stability.
    train_results = []
    for a in train_anchors:
        if verbose:
            print(f"\n[train] {a}")
        train_results.append(
            _score_anchor(a, epoch=epoch, hid_dim=hid_dim, gpu=gpu, verbose=verbose)
        )

    display_results = []
    for a in display_anchors:
        if a in train_anchors:
            display_results.append({"anchor_month": a, "reused_train": True})
            continue
        if verbose:
            print(f"\n[display] {a}")
        display_results.append(
            _score_anchor(a, epoch=epoch, hid_dim=hid_dim, gpu=gpu, verbose=verbose)
        )

    compare_report: dict[str, Any] | None = None
    if compare_others:
        from class_1_anomaly_detection.src.experiments.run_pygod_compare import (
            run_compare,
        )

        compare_report = {}
        for a in display_anchors:
            if verbose:
                print(f"\n[compare] {a} models={COMPARE_SLUGS}")
            compare_report[a] = run_compare(
                models=list(COMPARE_SLUGS),
                anchor_month=a,
                epoch=epoch,
                hid_dim=hid_dim,
                verbose=int(verbose),
            )

    manifest = {
        "production_model": PRODUCTION_SLUG,
        "train_anchor_months": train_anchors,
        "display_anchor_months": display_anchors,
        "train_cutoff": train_cutoff,
        "train_ratio": train_ratio,
        "epoch": epoch,
        "hid_dim": hid_dim,
        "gpu": gpu,
        "train_results": train_results,
        "display_results": display_results,
        "compare_others": bool(compare_others),
        "note": (
            "Production default remains gadnr unless PM updates "
            "shared_docs/structured/class_1_anomaly_spec.md."
        ),
    }
    ML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = ML_OUTPUT_DIR / "gadnr_production_manifest.json"
    write_json(out, manifest)
    if verbose:
        print(f"\n[saved] {out.relative_to(_REPO_ROOT)}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GAD-NR production train/display")
    parser.add_argument("--anchor-month", type=str, default=None)
    parser.add_argument("--all-anchors", action="store_true")
    parser.add_argument("--train-cutoff", type=str, default=None, help="YYYYMM inclusive")
    parser.add_argument("--train-ratio", type=float, default=0.5)
    parser.add_argument("--epoch", type=int, default=DEFAULT_EPOCH)
    parser.add_argument("--hid-dim", type=int, default=DEFAULT_HID_DIM)
    parser.add_argument("--gpu", type=int, default=-1, help="-1 CPU, 0+ CUDA device")
    parser.add_argument(
        "--compare-others",
        action="store_true",
        help="Also run non-production PyGOD models for confirmation",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    anchors = None
    if args.anchor_month:
        anchors = [normalize_anchor_month(args.anchor_month)]
    elif not args.all_anchors:
        # Default: latest ready anchor only
        ready = list_compare_ready_anchor_months()
        anchors = ready[-1:] if ready else None

    run_production(
        anchors=anchors,
        train_cutoff=args.train_cutoff,
        train_ratio=args.train_ratio,
        epoch=args.epoch,
        hid_dim=args.hid_dim,
        gpu=args.gpu,
        compare_others=args.compare_others,
        verbose=not args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
