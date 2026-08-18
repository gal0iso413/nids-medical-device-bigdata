"""Measure Class 1 3-month training-graph feasibility without slicing the graph.

This gate reads verified monthly facts, builds the same 3-month company-pair
model graph used by GAD-NR, and records node/edge counts, memory, and GAD-NR
wall time.  It never filters that training graph by region or item group, and
it is not an API or serving path.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import time
import tracemalloc
from typing import Any, Callable, Sequence

import pandas as pd

from class_1_anomaly_detection.src.model_pipeline import (
    build_gadnr_features,
    build_model_graph,
    run_gadnr,
)
from class_1_anomaly_detection.src.offline_anchor_runner import _months as _required_months
from data_pipeline.observability.scale_preflight import (
    REPOSITORY_ROOT,
    atomic_write_canonical_json,
)
from data_pipeline.storage.monthly_fact_parquet import (
    read_monthly_fact_partitions,
    verify_monthly_fact_partition,
)


REPORT_SCHEMA_VERSION = "1.0.0"
TRAINING_GRAPH_POLICY = {
    "slice_by_region": False,
    "slice_by_item_group": False,
    "note": "Failure does not authorize slicing the training graph by region or item group.",
}


class Class1GraphScaleGateError(RuntimeError):
    """Raised when the graph-scale gate cannot complete safely."""


class Class1GraphScaleGateConfigError(Class1GraphScaleGateError):
    """Raised for a malformed or unsafe graph-scale gate configuration."""


@dataclass(frozen=True)
class Class1GraphScaleGateConfig:
    parquet_root: Path
    anchor_month: str
    region_vocabulary: tuple[str, ...]
    seed: int
    report_label: str
    max_nodes: int
    max_edges: int
    max_peak_rss_bytes: int
    max_gadnr_seconds: float


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _is_inside_repository(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        return False
    return True


def _require_positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise Class1GraphScaleGateConfigError(f"{field} must be a positive integer")
    return value


def _require_positive_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise Class1GraphScaleGateConfigError(f"{field} must be a positive number")
    return float(value)


def _process_rss_bytes() -> int | None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            handle = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return int(counters.PeakWorkingSetSize)
        except Exception:
            return None
        return None
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(usage) if os.uname().sysname == "Darwin" else int(usage) * 1024
    except Exception:
        return None


def load_class1_graph_scale_gate_config(config_path: Path) -> Class1GraphScaleGateConfig:
    if not isinstance(config_path, Path):
        raise TypeError("config_path must be a pathlib.Path")
    if _is_inside_repository(config_path):
        raise Class1GraphScaleGateConfigError("graph-scale gate config must be outside the repository")
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Class1GraphScaleGateConfigError("could not read graph-scale gate config") from exc
    if not isinstance(payload, dict):
        raise Class1GraphScaleGateConfigError("graph-scale gate config must be a JSON object")
    required = {
        "parquet_root", "anchor_month", "region_vocabulary", "seed", "report_label",
        "max_nodes", "max_edges", "max_peak_rss_bytes", "max_gadnr_seconds",
    }
    unknown = set(payload) - required
    missing = required - set(payload)
    if missing or unknown:
        raise Class1GraphScaleGateConfigError(
            f"graph-scale gate config fields mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    parquet_root = Path(payload["parquet_root"])
    if not parquet_root.is_absolute():
        parquet_root = (config_path.parent / parquet_root).resolve()
    if _is_inside_repository(parquet_root):
        raise Class1GraphScaleGateConfigError("parquet_root must be outside the repository")
    vocabulary = payload["region_vocabulary"]
    if not isinstance(vocabulary, list) or not all(isinstance(item, str) and item.strip() for item in vocabulary):
        raise Class1GraphScaleGateConfigError("region_vocabulary must be a non-empty string array")
    if sorted(set(vocabulary)) != vocabulary:
        raise Class1GraphScaleGateConfigError("region_vocabulary must be unique and sorted")
    report_label = payload["report_label"]
    if not isinstance(report_label, str) or not report_label.strip() or len(report_label) > 80:
        raise Class1GraphScaleGateConfigError("report_label must be a non-empty string of at most 80 characters")
    if any(character in report_label for character in ("/", "\\", "\r", "\n")):
        raise Class1GraphScaleGateConfigError("report_label must not contain a path separator or newline")
    seed = payload["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise Class1GraphScaleGateConfigError("seed must be a non-negative integer")
    return Class1GraphScaleGateConfig(
        parquet_root=parquet_root,
        anchor_month=str(payload["anchor_month"]),
        region_vocabulary=tuple(vocabulary),
        seed=seed,
        report_label=report_label.strip(),
        max_nodes=_require_positive_int(payload["max_nodes"], "max_nodes"),
        max_edges=_require_positive_int(payload["max_edges"], "max_edges"),
        max_peak_rss_bytes=_require_positive_int(payload["max_peak_rss_bytes"], "max_peak_rss_bytes"),
        max_gadnr_seconds=_require_positive_number(payload["max_gadnr_seconds"], "max_gadnr_seconds"),
    )


def _validate_report_path(report_path: Path) -> Path:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a pathlib.Path")
    if _is_inside_repository(report_path):
        raise Class1GraphScaleGateError("graph-scale gate report must be outside the repository")
    if not report_path.parent.is_dir():
        raise Class1GraphScaleGateError("graph-scale gate report parent must already exist")
    return report_path.resolve()


def _peak_rss(observed: int | None) -> int | None:
    current = _process_rss_bytes()
    if observed is None:
        return current
    if current is None:
        return observed
    return max(observed, current)


def run_class1_graph_scale_gate(
    config: Class1GraphScaleGateConfig,
    report_path: Path,
    *,
    scorer: Callable[[pd.DataFrame, tuple[tuple[int, ...], tuple[int, ...]]], list[float]] | None = None,
) -> dict[str, Any]:
    """Measure the unsliced 3-month training graph and GAD-NR cost."""
    report_path = _validate_report_path(report_path)
    try:
        months = _required_months(config.anchor_month)
    except Exception as exc:
        raise Class1GraphScaleGateError("anchor_month must be YYYYMM") from exc
    try:
        for month in months:
            verify_monthly_fact_partition(config.parquet_root, month)
        fact = read_monthly_fact_partitions(config.parquet_root, months=months)
    except Exception as exc:
        raise Class1GraphScaleGateError("all six required monthly partitions must exist and pass checksum verification") from exc

    tracing_was_active = tracemalloc.is_tracing()
    if not tracing_was_active:
        tracemalloc.start()
    tracemalloc.reset_peak()
    peak_rss = _process_rss_bytes()
    fail_reasons: list[str] = []
    gadnr_seconds: float | None = None
    gadnr_status = "not_run"
    graph_seconds: float | None = None
    feature_seconds: float | None = None
    node_count: int | None = None
    edge_count: int | None = None
    self_loop_count: int | None = None
    window_months: tuple[str, ...] = ()
    traced_peak = 0
    try:
        graph_started = time.perf_counter()
        graph = build_model_graph(fact, anchor_month=config.anchor_month)
        graph_seconds = time.perf_counter() - graph_started
        peak_rss = _peak_rss(peak_rss)
        window_months = graph.window_months
        node_count = len(graph.nodes)
        edge_count = int(len(graph.edges))
        self_loop_count = int(graph.self_loop_count)
        if node_count > config.max_nodes:
            fail_reasons.append("over_max_nodes")
        if edge_count > config.max_edges:
            fail_reasons.append("over_max_edges")
        if not fail_reasons:
            feature_started = time.perf_counter()
            features, _manifest = build_gadnr_features(
                fact, graph, region_vocabulary=config.region_vocabulary,
            )
            feature_seconds = time.perf_counter() - feature_started
            peak_rss = _peak_rss(peak_rss)
            gadnr_started = time.perf_counter()
            try:
                scores = run_gadnr(features, graph, scorer=scorer, seed=config.seed)
            except Exception:
                gadnr_status = "failed"
                fail_reasons.append("gadnr_failed")
                scores = []
            gadnr_seconds = time.perf_counter() - gadnr_started
            peak_rss = _peak_rss(peak_rss)
            if gadnr_status != "failed":
                if len(scores) != node_count:
                    gadnr_status = "failed"
                    fail_reasons.append("gadnr_failed")
                else:
                    gadnr_status = "completed"
                    if gadnr_seconds > config.max_gadnr_seconds:
                        fail_reasons.append("over_max_gadnr_seconds")
        if peak_rss is not None and peak_rss > config.max_peak_rss_bytes:
            fail_reasons.append("over_max_peak_rss_bytes")
        _, traced_peak = tracemalloc.get_traced_memory()
    finally:
        if not tracing_was_active:
            tracemalloc.stop()

    unique_reasons = tuple(dict.fromkeys(fail_reasons))
    status = "fail" if unique_reasons else "pass"
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_kind": "class1_graph_scale_gate",
        "report_label": config.report_label,
        "status": status,
        "fail_reasons": list(unique_reasons),
        "anchor_month": config.anchor_month,
        "window_months": list(window_months),
        "required_months": list(months),
        "training_graph_policy": TRAINING_GRAPH_POLICY,
        "ceilings": {
            "max_nodes": config.max_nodes,
            "max_edges": config.max_edges,
            "max_peak_rss_bytes": config.max_peak_rss_bytes,
            "max_gadnr_seconds": config.max_gadnr_seconds,
        },
        "graph": {
            "node_count": node_count,
            "edge_count": edge_count,
            "self_loop_count": self_loop_count,
            "sliced_by_region": False,
            "sliced_by_item_group": False,
        },
        "timing": {
            "graph_build_seconds": None if graph_seconds is None else round(graph_seconds, 6),
            "feature_build_seconds": None if feature_seconds is None else round(feature_seconds, 6),
            "gadnr_seconds": None if gadnr_seconds is None else round(gadnr_seconds, 6),
            "gadnr_status": gadnr_status,
        },
        "memory": {
            "peak_rss_bytes": peak_rss,
            "tracemalloc_peak_bytes": traced_peak,
            "tracemalloc_note": "Python allocation peak only; it does not represent total native process memory.",
        },
        "environment": {
            "python_version": platform.python_version(),
            "os_family": platform.system(),
            "cpu_logical_count": os.cpu_count(),
        },
        "model_settings": {
            "primary_model": "gadnr",
            "seed": config.seed,
            "batch_size": 0,
            "epoch": 100,
            "num_layers": 1,
        },
    }
    atomic_write_canonical_json(report_path, payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure Class 1 3-month GAD-NR graph-scale feasibility.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        payload = run_class1_graph_scale_gate(
            load_class1_graph_scale_gate_config(args.config), args.report,
        )
    except Class1GraphScaleGateError as exc:
        print(_canonical_json_bytes({"status": "error", "error": type(exc).__name__}).decode("utf-8"))
        del exc
        return 3
    print(_canonical_json_bytes({"status": payload["status"], "report_kind": payload["report_kind"]}).decode("utf-8"))
    return 0 if payload["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
