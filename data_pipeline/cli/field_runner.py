"""Offline Windows field-run commands over the existing pipeline contracts."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import tempfile
from typing import Any, Final, Sequence, TextIO

from data_pipeline.checkpoints import (
    derive_supply_monthly_run_id,
    verify_sealed_supply_checkpoint,
)
from data_pipeline.checkpoints.supply_monthly import (
    CHECKPOINT_CONTRACT_VERSION,
    DATABASE_FILENAME as CHECKPOINT_DATABASE_FILENAME,
    DATASET_NAME as CHECKPOINT_DATASET_NAME,
    RUN_MANIFEST_FILENAME,
    SEALED_MANIFEST_FILENAME,
)
from data_pipeline.ingest import create_source_lineage
from data_pipeline.orchestration import run_supply_monthly_orchestration
from data_pipeline.orchestration.supply_monthly import COMPLETE_MANIFEST_FILENAME
from data_pipeline.storage import (
    build_master_product_lookup,
    create_master_lineage,
    verify_master_product_lookup,
)
from data_pipeline.storage.master_product_lookup import (
    DATABASE_FILENAME as MASTER_DATABASE_FILENAME,
    DATASET_NAME as MASTER_DATASET_NAME,
    LOGICAL_SCHEMA_VERSION as MASTER_SCHEMA_VERSION,
    MANIFEST_FILENAME as MASTER_MANIFEST_FILENAME,
)

from .config import FieldRunConfig, FieldRunConfigError, load_field_run_config


EXIT_OK: Final = 0
EXIT_CONFIG: Final = 3
EXIT_PREFLIGHT: Final = 4
EXIT_RUN: Final = 5
EXIT_VERIFY: Final = 6
DIAGNOSTIC_LIMIT: Final = 20
_PACKAGE_RANGES: Final = {
    "pandas": ((2, 2, 0), (3, 1, 0)),
    "pyarrow": ((24, 0, 0), (25, 0, 0)),
    "openpyxl": ((3, 1, 5), (4, 0, 0)),
}


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    detail: str
    hint: str | None = None


@dataclass(frozen=True)
class PreflightReport:
    ok: bool
    checks: tuple[PreflightCheck, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "command": "preflight",
            "ok": self.ok,
            "checks": [asdict(check) for check in self.checks],
        }


def _version_tuple(value: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", value)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def _check_packages() -> list[PreflightCheck]:
    checks = [
        PreflightCheck(
            "python_version",
            "pass" if sys.version_info >= (3, 11) else "fail",
            f"Python {platform.python_version()}",
            None if sys.version_info >= (3, 11) else "Install an approved Python 3.11+ runtime offline.",
        )
    ]
    for name, (minimum, maximum) in _PACKAGE_RANGES.items():
        try:
            installed = package_version(name)
        except PackageNotFoundError:
            checks.append(
                PreflightCheck(
                    f"package_{name}",
                    "fail",
                    "not installed",
                    "Install the approved offline data-pipeline dependency bundle.",
                )
            )
            continue
        parsed = _version_tuple(installed)
        supported = parsed is not None and minimum <= parsed < maximum
        checks.append(
            PreflightCheck(
                f"package_{name}",
                "pass" if supported else "fail",
                f"{name} {installed}",
                None if supported else f"Use a version in [{'.'.join(map(str, minimum))}, {'.'.join(map(str, maximum))}).",
            )
        )
    return checks


def _sample_names(paths: Sequence[Path], *, total: int | None = None) -> str:
    names = [path.name or "<unnamed>" for path in paths[:DIAGNOSTIC_LIMIT]]
    total = len(paths) if total is None else total
    omitted = max(total - len(names), 0)
    suffix = f"; omitted={omitted}" if omitted else ""
    return f"total={total}; sample={names}{suffix}"


def _check_readable_inputs(paths: Sequence[Path], name: str) -> PreflightCheck:
    invalid_sample: list[Path] = []
    invalid_count = 0
    for path in paths:
        try:
            if not path.is_file():
                invalid_count += 1
                if len(invalid_sample) < DIAGNOSTIC_LIMIT:
                    invalid_sample.append(path)
                continue
            with path.open("rb") as stream:
                stream.read(1)
        except OSError:
            invalid_count += 1
            if len(invalid_sample) < DIAGNOSTIC_LIMIT:
                invalid_sample.append(path)
    if invalid_count:
        return PreflightCheck(
            name,
            "fail",
            _sample_names(invalid_sample, total=invalid_count),
            "Confirm the listed logical filenames exist and are readable by this account.",
        )
    return PreflightCheck(name, "pass", f"readable_files={len(paths)}")


def _nearest_existing_parent(path: Path) -> Path | None:
    candidate = path.resolve(strict=False)
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate if candidate.exists() and candidate.is_dir() else None


def _check_writable_root(path: Path, name: str) -> PreflightCheck:
    parent = _nearest_existing_parent(path)
    if parent is None:
        return PreflightCheck(
            name,
            "fail",
            "no existing writable ancestor",
            "Create an approved parent directory and grant the runner write access.",
        )
    try:
        with tempfile.NamedTemporaryFile(prefix=".nids-write-probe-", dir=parent):
            pass
    except OSError:
        return PreflightCheck(
            name,
            "fail",
            "write probe failed",
            "Grant write/delete access on the configured root or its nearest existing parent.",
        )
    return PreflightCheck(name, "pass", "temporary write/delete probe passed")


def _normalized_overlap(first: Path, second: Path) -> bool:
    left = os.path.normcase(str(first.resolve(strict=False)))
    right = os.path.normcase(str(second.resolve(strict=False)))
    try:
        common = os.path.commonpath((left, right))
    except ValueError:
        return False
    return common in {left, right}


def _check_disk(path: Path, name: str, minimum_free_bytes: int) -> PreflightCheck:
    parent = _nearest_existing_parent(path)
    if parent is None:
        return PreflightCheck(name, "fail", "disk volume unavailable")
    try:
        free = shutil.disk_usage(parent).free
    except OSError:
        return PreflightCheck(name, "fail", "could not read disk free space")
    if minimum_free_bytes == 0:
        return PreflightCheck(
            name,
            "warn",
            f"free_bytes={free}; minimum_free_bytes is not configured",
            "Set a site-approved minimum_free_bytes before a production run.",
        )
    return PreflightCheck(
        name,
        "pass" if free >= minimum_free_bytes else "fail",
        f"free_bytes={free}; required_bytes={minimum_free_bytes}",
        None if free >= minimum_free_bytes else "Free space or choose an approved larger volume.",
    )


def _windows_long_paths_enabled() -> bool | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
        return value == 1
    except OSError:
        return False


def _check_long_paths(config: FieldRunConfig) -> PreflightCheck:
    if os.name != "nt":
        return PreflightCheck("windows_long_paths", "pass", "not a Windows runtime")
    candidates = [
        *config.supply_workbooks,
        *config.master_workbooks,
        config.master_lookup_root,
        config.checkpoint_root,
        config.output_root,
    ]
    # Reserve space for contracted dataset/version/run/month suffixes.
    projected = max(len(str(path.resolve(strict=False))) for path in candidates) + 190
    enabled = _windows_long_paths_enabled()
    at_risk = projected >= 240 and not enabled
    return PreflightCheck(
        "windows_long_paths",
        "warn" if at_risk else "pass",
        f"long_paths_enabled={bool(enabled)}; projected_max_chars={projected}",
        "Enable the approved Windows long-path policy or choose shorter roots."
        if at_risk
        else None,
    )


def _master_lookup_dir(config: FieldRunConfig, source_hash: str) -> Path:
    return (
        config.master_lookup_root
        / MASTER_DATASET_NAME
        / f"schema_version={MASTER_SCHEMA_VERSION}"
        / f"source_hash={source_hash}"
    )


def _check_master_mode(config: FieldRunConfig) -> list[PreflightCheck]:
    if config.uses_master_workbooks:
        return [
            _check_readable_inputs(config.master_workbooks, "master_workbooks"),
            _check_writable_root(config.master_lookup_root, "master_lookup_root_writable"),
        ]
    assert config.master_source_hash is not None
    lookup_dir = _master_lookup_dir(config, config.master_source_hash)
    missing = [
        name
        for name in (MASTER_DATABASE_FILENAME, MASTER_MANIFEST_FILENAME)
        if not lookup_dir.joinpath(name).is_file()
    ]
    return [
        PreflightCheck(
            "published_master_lookup",
            "fail" if missing else "pass",
            "missing=" + repr(missing) if missing else "database and manifest present; checksum deferred",
            "Build or copy the immutable lookup before running." if missing else None,
        )
    ]


def _checkpoint_inventory(config: FieldRunConfig) -> PreflightCheck:
    root = (
        config.checkpoint_root
        / CHECKPOINT_DATASET_NAME
        / f"checkpoint_version={CHECKPOINT_CONTRACT_VERSION}"
    )
    counts = {"active": 0, "sealed": 0, "complete": 0, "incomplete": 0}
    try:
        directories = root.glob("run_id=*") if root.is_dir() else ()
        for run_dir in directories:
            if run_dir.joinpath(COMPLETE_MANIFEST_FILENAME).is_file():
                counts["complete"] += 1
            elif run_dir.joinpath(SEALED_MANIFEST_FILENAME).is_file():
                counts["sealed"] += 1
            elif run_dir.joinpath(CHECKPOINT_DATABASE_FILENAME).is_file() and run_dir.joinpath(RUN_MANIFEST_FILENAME).is_file():
                counts["active"] += 1
            else:
                counts["incomplete"] += 1
    except OSError:
        return PreflightCheck("checkpoint_inventory", "fail", "could not inspect checkpoint root")
    status = "warn" if counts["incomplete"] else "pass"
    return PreflightCheck(
        "checkpoint_inventory",
        status,
        "; ".join(f"{key}={value}" for key, value in counts.items()),
        "Inspect incomplete artifacts manually; the CLI never deletes or resets them."
        if counts["incomplete"]
        else None,
    )


def run_preflight(config: FieldRunConfig) -> PreflightReport:
    """Perform bounded, light checks without Excel traversal or full checksums."""

    checks = _check_packages()
    checks.append(_check_readable_inputs(config.supply_workbooks, "supply_workbooks"))
    checks.extend(_check_master_mode(config))
    overlap = _normalized_overlap(config.checkpoint_root, config.output_root)
    checks.append(
        PreflightCheck(
            "checkpoint_output_disjoint",
            "fail" if overlap else "pass",
            "paths overlap" if overlap else "paths are distinct and non-nested",
            "Choose separate, non-nested checkpoint and output roots." if overlap else None,
        )
    )
    checks.extend(
        [
            _check_writable_root(config.checkpoint_root, "checkpoint_root_writable"),
            _check_writable_root(config.output_root, "output_root_writable"),
            _check_disk(config.checkpoint_root, "checkpoint_disk_space", config.minimum_free_bytes),
            _check_disk(config.output_root, "output_disk_space", config.minimum_free_bytes),
            _check_long_paths(config),
            _checkpoint_inventory(config),
        ]
    )
    return PreflightReport(
        ok=not any(check.status == "fail" for check in checks),
        checks=tuple(checks),
    )


def _master_source_hash(config: FieldRunConfig, *, build: bool) -> str:
    if config.uses_master_workbooks:
        if build:
            return build_master_product_lookup(
                config.master_workbooks,
                config.master_lookup_root,
                batch_size=config.batch_size,
            ).source_hash
        return create_master_lineage(config.master_workbooks).source_hash
    assert config.master_source_hash is not None
    return config.master_source_hash


def _runtime_identity(config: FieldRunConfig) -> tuple[str, str]:
    supply_lineage = create_source_lineage(config.supply_workbooks)
    source_hash = _master_source_hash(config, build=False)
    master = verify_master_product_lookup(config.master_lookup_root, source_hash)
    return derive_supply_monthly_run_id(supply_lineage, master), source_hash


def _run_dir(config: FieldRunConfig, run_id: str) -> Path:
    return (
        config.checkpoint_root
        / CHECKPOINT_DATASET_NAME
        / f"checkpoint_version={CHECKPOINT_CONTRACT_VERSION}"
        / f"run_id={run_id}"
    )


def run_pipeline(config: FieldRunConfig) -> dict[str, Any]:
    report = run_preflight(config)
    if not report.ok:
        raise FieldRunnerPreflightError(report)
    source_hash = _master_source_hash(config, build=True)
    result = run_supply_monthly_orchestration(
        supply_paths=config.supply_workbooks,
        master_lookup_root=config.master_lookup_root,
        master_source_hash=source_hash,
        checkpoint_root=config.checkpoint_root,
        output_root=config.output_root,
        max_month_fact_bytes=config.max_month_fact_bytes,
        batch_size=config.batch_size,
    )
    return {
        "command": "run",
        "status": result.status,
        "run_id": result.run_id,
        "written_months": list(result.written_months),
        "unchanged_months": list(result.unchanged_months),
        "skipped_unmatched_only_months": list(result.skipped_unmatched_only_months),
        "relative_complete_manifest_path": result.relative_complete_manifest_path,
    }


def read_status(config: FieldRunConfig) -> dict[str, Any]:
    source_hash = _master_source_hash(config, build=False)
    lookup_dir = _master_lookup_dir(config, source_hash)
    if not all(
        lookup_dir.joinpath(filename).is_file()
        for filename in (MASTER_DATABASE_FILENAME, MASTER_MANIFEST_FILENAME)
    ):
        return {
            "command": "status",
            "run_id": None,
            "state": "master_lookup_missing",
            "verified": False,
        }
    run_id, _ = _runtime_identity(config)
    run_dir = _run_dir(config, run_id)
    if run_dir.joinpath(COMPLETE_MANIFEST_FILENAME).is_file():
        state = "complete_unverified"
    elif run_dir.joinpath(SEALED_MANIFEST_FILENAME).is_file():
        state = "sealed_unpublished_or_incomplete"
    elif run_dir.joinpath(CHECKPOINT_DATABASE_FILENAME).is_file() and run_dir.joinpath(RUN_MANIFEST_FILENAME).is_file():
        state = "active"
    elif run_dir.exists():
        state = "incomplete_artifact"
    else:
        state = "not_started"
    return {"command": "status", "run_id": run_id, "state": state, "verified": False}


def verify_completed_run(config: FieldRunConfig) -> dict[str, Any]:
    run_id, source_hash = _runtime_identity(config)
    run_dir = _run_dir(config, run_id)
    if not run_dir.joinpath(COMPLETE_MANIFEST_FILENAME).is_file():
        raise FieldRunVerificationError("The complete manifest is not present")
    if not run_dir.joinpath(SEALED_MANIFEST_FILENAME).is_file():
        raise FieldRunVerificationError("The sealed checkpoint manifest is not present")
    sealed = verify_sealed_supply_checkpoint(config.checkpoint_root, run_id)
    # In a complete, verified-sealed state the existing orchestration follows its
    # read/verify-only path and must return unchanged.
    result = run_supply_monthly_orchestration(
        supply_paths=config.supply_workbooks,
        master_lookup_root=config.master_lookup_root,
        master_source_hash=source_hash,
        checkpoint_root=config.checkpoint_root,
        output_root=config.output_root,
        max_month_fact_bytes=config.max_month_fact_bytes,
        batch_size=config.batch_size,
    )
    if result.status != "unchanged":
        raise FieldRunVerificationError("Verification unexpectedly changed run state")
    return {
        "command": "verify",
        "status": "verified",
        "run_id": run_id,
        "months": list(sealed.months),
        "ledger_rows": sealed.ledger_rows,
        "matched_rows": sealed.matched_rows,
        "unmatched_rows": sealed.unmatched_rows,
    }


class FieldRunnerPreflightError(RuntimeError):
    def __init__(self, report: PreflightReport) -> None:
        super().__init__("Preflight checks failed")
        self.report = report


class FieldRunVerificationError(RuntimeError):
    """Raised when a completed run cannot be verified without mutation."""


def _safe_error_message(exc: BaseException, config: FieldRunConfig | None) -> str:
    message = str(exc) or type(exc).__name__
    if config is not None:
        paths = (
            *config.supply_workbooks,
            *config.master_workbooks,
            config.master_lookup_root,
            config.checkpoint_root,
            config.output_root,
            config.config_path,
        )
        for path in paths:
            for raw in {str(path), str(path.resolve(strict=False))}:
                if raw:
                    message = message.replace(raw, f"<{path.name or 'configured-path'}>")
    return message[:2000]


def _write_json(stream: TextIO, payload: dict[str, Any]) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m data_pipeline.cli",
        description="Run and verify the offline monthly supply pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("preflight", "run", "status", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", required=True, type=Path)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    args = _parser().parse_args(argv)
    config: FieldRunConfig | None = None
    try:
        config = load_field_run_config(args.config)
        if args.command == "preflight":
            report = run_preflight(config)
            _write_json(stdout, report.payload())
            return EXIT_OK if report.ok else EXIT_PREFLIGHT
        if args.command == "run":
            _write_json(stdout, run_pipeline(config))
            return EXIT_OK
        if args.command == "status":
            _write_json(stdout, read_status(config))
            return EXIT_OK
        _write_json(stdout, verify_completed_run(config))
        return EXIT_OK
    except KeyboardInterrupt:
        _write_json(
            stderr,
            {
                "error": "interrupted",
                "hint": "Rerun the same command with the unchanged config to resume safely.",
                "stage": args.command,
            },
        )
        return 130
    except FieldRunConfigError as exc:
        _write_json(
            stderr,
            {"error": type(exc).__name__, "message": str(exc), "stage": "config"},
        )
        return EXIT_CONFIG
    except FieldRunnerPreflightError as exc:
        _write_json(stderr, exc.report.payload())
        return EXIT_PREFLIGHT
    except Exception as exc:
        _write_json(
            stderr,
            {
                "error": type(exc).__name__,
                "message": _safe_error_message(exc, config),
                "hint": "Keep existing artifacts unchanged, correct the reported cause, and rerun with the same config.",
                "stage": args.command,
            },
        )
        return EXIT_VERIFY if args.command == "verify" else EXIT_RUN
