"""Bounded, read-only supply Excel benchmark for onsite scale readiness."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time
import tracemalloc
from typing import Any, Sequence

from data_pipeline.ingest import stream_nids_supply_excel


REPORT_SCHEMA_VERSION = "1.0.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class ScalePreflightError(RuntimeError):
    """Raised when a bounded scale-readiness measurement cannot complete safely."""


class ScalePreflightConfigError(ScalePreflightError):
    """Raised for a malformed or unsafe scale-readiness configuration."""


@dataclass(frozen=True)
class ScalePreflightConfig:
    supply_workbooks: tuple[Path, ...]
    sample_max_workbooks: int
    sample_max_rows_per_workbook: int
    batch_size: int
    expected_total_supply_rows: int | None
    report_label: str


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _is_inside_repository(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        return False
    return True


def _require_positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ScalePreflightConfigError(f"{field} must be a positive integer")
    return value


def _resolve_paths(value: Any, *, base: Path, field: str) -> tuple[Path, ...]:
    if not isinstance(value, list) or not value:
        raise ScalePreflightConfigError(f"{field} must be a non-empty array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ScalePreflightConfigError(f"{field} must contain non-empty strings")
    paths = tuple((base / item).resolve() if not Path(item).is_absolute() else Path(item).resolve() for item in value)
    if len(set(paths)) != len(paths):
        raise ScalePreflightConfigError(f"{field} must not contain duplicate paths")
    return paths


def load_scale_preflight_config(config_path: Path) -> ScalePreflightConfig:
    """Load the small explicit benchmark configuration from outside the repository."""
    if not isinstance(config_path, Path):
        raise TypeError("config_path must be a pathlib.Path")
    if _is_inside_repository(config_path):
        raise ScalePreflightConfigError("scale-preflight config must be outside the repository")
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScalePreflightConfigError("could not read scale-preflight config") from exc
    if not isinstance(payload, dict):
        raise ScalePreflightConfigError("scale-preflight config must be a JSON object")
    required = {
        "supply_workbooks",
        "sample_max_workbooks",
        "sample_max_rows_per_workbook",
        "batch_size",
        "report_label",
    }
    allowed = required | {"expected_total_supply_rows"}
    missing = required - set(payload)
    unknown = set(payload) - allowed
    if missing or unknown:
        raise ScalePreflightConfigError(
            f"scale-preflight config fields mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    report_label = payload["report_label"]
    if not isinstance(report_label, str) or not report_label.strip() or len(report_label) > 80:
        raise ScalePreflightConfigError("report_label must be a non-empty string of at most 80 characters")
    if any(character in report_label for character in ("/", "\\", "\r", "\n")):
        raise ScalePreflightConfigError("report_label must not contain a path separator or newline")
    expected = payload.get("expected_total_supply_rows")
    if expected is not None:
        expected = _require_positive_int(expected, "expected_total_supply_rows")
    return ScalePreflightConfig(
        supply_workbooks=_resolve_paths(
            payload["supply_workbooks"], base=config_path.parent, field="supply_workbooks"
        ),
        sample_max_workbooks=_require_positive_int(payload["sample_max_workbooks"], "sample_max_workbooks"),
        sample_max_rows_per_workbook=_require_positive_int(
            payload["sample_max_rows_per_workbook"], "sample_max_rows_per_workbook"
        ),
        batch_size=_require_positive_int(payload["batch_size"], "batch_size"),
        expected_total_supply_rows=expected,
        report_label=report_label.strip(),
    )


def _validate_report_path(report_path: Path) -> Path:
    if not isinstance(report_path, Path):
        raise TypeError("report_path must be a pathlib.Path")
    if _is_inside_repository(report_path):
        raise ScalePreflightError("scale-preflight report must be outside the repository")
    parent = report_path.parent
    if not parent.is_dir():
        raise ScalePreflightError("scale-preflight report parent must already exist")
    return report_path.resolve()


def _input_bytes(paths: Sequence[Path]) -> int:
    total = 0
    for path in paths:
        try:
            if not path.is_file():
                raise OSError("not a file")
            total += path.stat().st_size
        except OSError as exc:
            raise ScalePreflightError("configured supply workbook is not readable") from exc
    return total


def _workbook_measurement(
    workbook: Path,
    *,
    index: int,
    batch_size: int,
    max_rows: int,
) -> tuple[dict[str, Any], int]:
    started = time.perf_counter()
    max_batch_memory = 0
    with stream_nids_supply_excel(
        [workbook],
        batch_size=batch_size,
        max_rows_per_workbook=max_rows,
        create_source_lineage_snapshot=False,
    ) as stream:
        for batch in stream:
            max_batch_memory = max(
                max_batch_memory, int(batch.memory_usage(index=True, deep=True).sum())
            )
    elapsed = time.perf_counter() - started
    report = stream.report
    report.validate_accounting()
    if report.rows_read == 0:
        raise ScalePreflightError("sample workbook contained no non-empty source rows")
    emitted_per_second = report.rows_emitted / elapsed if elapsed > 0 else 0.0
    return (
        {
            "workbook_index": index,
            "byte_size": workbook.stat().st_size,
            "rows_read": report.rows_read,
            "rows_emitted": report.rows_emitted,
            "rows_rejected": report.rows_rejected,
            "rejected_by_reason": dict(sorted(report.rejected_by_reason.items())),
            "wall_seconds": round(elapsed, 6),
            "emitted_rows_per_second": round(emitted_per_second, 6),
        },
        max_batch_memory,
    )


def atomic_write_canonical_json(path: Path, payload: dict[str, Any]) -> None:
    """Write canonical report JSON through a sibling temporary file."""
    temp_path: Path | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.tmp-", suffix=".json", dir=path.parent
        )
        temp_path = Path(temporary)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_canonical_json_bytes(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def run_scale_preflight(config: ScalePreflightConfig, report_path: Path) -> dict[str, Any]:
    """Measure a bounded sample without lineage hashes, joins, checkpoints, or writes."""
    report_path = _validate_report_path(report_path)
    ordered = tuple(sorted(config.supply_workbooks, key=lambda path: (path.name.casefold(), path.name)))
    selected = ordered[: config.sample_max_workbooks]
    if not selected:
        raise ScalePreflightError("no supply workbooks were selected")
    total_input_bytes = _input_bytes(ordered)
    tracing_was_active = tracemalloc.is_tracing()
    if not tracing_was_active:
        tracemalloc.start()
    tracemalloc.reset_peak()
    measurements: list[dict[str, Any]] = []
    max_batch_memory = 0
    started = time.perf_counter()
    try:
        for index, workbook in enumerate(selected, start=1):
            measurement, batch_memory = _workbook_measurement(
                workbook,
                index=index,
                batch_size=config.batch_size,
                max_rows=config.sample_max_rows_per_workbook,
            )
            measurements.append(measurement)
            max_batch_memory = max(max_batch_memory, batch_memory)
        total_elapsed = time.perf_counter() - started
        rows_read = sum(item["rows_read"] for item in measurements)
        rows_emitted = sum(item["rows_emitted"] for item in measurements)
        rows_rejected = sum(item["rows_rejected"] for item in measurements)
        rejected = Counter()
        for item in measurements:
            rejected.update(item["rejected_by_reason"])
        throughput = rows_emitted / total_elapsed if total_elapsed > 0 else 0.0
        if throughput <= 0:
            raise ScalePreflightError("sample emitted zero throughput")
        _, traced_peak = tracemalloc.get_traced_memory()
    finally:
        if not tracing_was_active:
            tracemalloc.stop()
    eta: dict[str, Any] | None = None
    if config.expected_total_supply_rows is not None:
        eta = {
            "method": "simple_linear_sample_extrapolation",
            "expected_total_supply_rows": config.expected_total_supply_rows,
            "estimated_seconds": round(config.expected_total_supply_rows / throughput, 6),
            "note": "This is a sample-based linear estimate, not a prediction or execution approval.",
        }
    try:
        report_free_bytes = shutil.disk_usage(report_path.parent).free
    except OSError as exc:
        raise ScalePreflightError("could not inspect report output disk space") from exc
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_kind": "scale_readiness_preflight",
        "read_only_benchmark": True,
        "report_label": config.report_label,
        "sampling": {
            "selected_workbook_count": len(selected),
            "configured_workbook_count": len(ordered),
            "sample_max_workbooks": config.sample_max_workbooks,
            "sample_max_rows_per_workbook": config.sample_max_rows_per_workbook,
            "batch_size": config.batch_size,
        },
        "environment": {
            "python_version": platform.python_version(),
            "os_family": platform.system(),
            "cpu_logical_count": os.cpu_count(),
            "input_file_total_bytes": total_input_bytes,
            "report_output_free_bytes": report_free_bytes,
        },
        "measurement": {
            "rows_read": rows_read,
            "rows_emitted": rows_emitted,
            "rows_rejected": rows_rejected,
            "rejected_by_reason": dict(sorted(rejected.items())),
            "wall_seconds": round(total_elapsed, 6),
            "emitted_rows_per_second": round(throughput, 6),
            "max_batch_deep_memory_bytes": max_batch_memory,
            "tracemalloc_peak_bytes": traced_peak,
            "tracemalloc_note": "Python allocation peak only; it does not represent total native process memory.",
        },
        "workbooks": measurements,
        "eta": eta,
    }
    atomic_write_canonical_json(report_path, payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a bounded read-only scale readiness benchmark.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run_scale_preflight(load_scale_preflight_config(args.config), args.report)
    except ScalePreflightError as exc:
        print(json.dumps({"status": "error", "error": type(exc).__name__}, separators=(",", ":")), file=sys.stderr)
        return 3
    print(json.dumps({"status": "written", "report_kind": payload["report_kind"]}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
