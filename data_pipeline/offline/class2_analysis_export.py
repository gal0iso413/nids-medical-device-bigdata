"""Publish a local-only Class 2 analysis JSON from verified monthly partitions.

The browser consumes the PR #15 serializer payload at the existing
``/generated/class2-analysis.json`` adapter path.  This module is intentionally
an offline CLI/library: it has no HTTP, database, authentication, or release
suppression implementation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from typing import Any, Final, Iterable, Literal

import pandas as pd

from data_pipeline.aggregates.class2_analysis import build_class2_analysis
from data_pipeline.contracts.class2_analysis import (
    CLASS2_ANALYSIS_SCHEMA_VERSION,
    Class2AnalysisTables,
    serialize_class2_analysis,
)
from data_pipeline.contracts.supply_monthly import FACT_SCHEMA_VERSION, empty_monthly_fact
from data_pipeline.storage.monthly_fact_parquet import (
    InvalidPartitionRequestError,
    PartitionVerification,
    read_monthly_fact_partitions,
    verify_monthly_fact_partition,
)


EXPORT_SCHEMA_VERSION: Final = "1.0.0"
PAYLOAD_FILENAME: Final = "class2-analysis.json"
MANIFEST_FILENAME: Final = "class2-analysis-manifest.json"
DEFAULT_WEB_PUBLIC_ROOT: Final = Path("web/class2_public/public")
_MONTH_PATTERN: Final = re.compile(r"^\d{6}$")
_SPACE_PATTERN: Final = re.compile(r"\s+")
_STATES: Final = frozenset({"available", "suppressed", "not_available"})


class Class2OfflineExportError(RuntimeError):
    """Raised when a local analysis export cannot be safely produced."""


class Class2OfflineExportConflictError(Class2OfflineExportError):
    """Raised rather than replacing an existing different local artifact."""


@dataclass(frozen=True)
class Class2SelectionRequest:
    """One source-label selection; item names always retain their parent scope."""

    selection_type: Literal["item_group", "item_name"]
    label: str
    parent_item_group_label: str | None = None


@dataclass(frozen=True)
class Class2OfflineExportResult:
    status: Literal["written", "recovered", "unchanged"]
    output_path: Path
    manifest_path: Path
    payload_sha256: str
    export_state: str


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return sha256(_canonical_json_bytes(value)).hexdigest()


def _normalize_label(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _SPACE_PATTERN.sub(" ", unicodedata.normalize("NFKC", str(value)).strip()).casefold()
    return normalized or None


def _months(period_start: str, period_end: str) -> tuple[str, ...]:
    if not _MONTH_PATTERN.fullmatch(period_start) or not _MONTH_PATTERN.fullmatch(period_end):
        raise Class2OfflineExportError("period bounds must be YYYYMM")
    try:
        periods = pd.period_range(period_start, period_end, freq="M")
    except ValueError as exc:
        raise Class2OfflineExportError("period bounds are invalid") from exc
    if not len(periods):
        raise Class2OfflineExportError("period bounds are invalid")
    return tuple(period.strftime("%Y%m") for period in periods)


def _validate_selections(selections: Iterable[Class2SelectionRequest]) -> tuple[Class2SelectionRequest, ...]:
    result: list[Class2SelectionRequest] = []
    seen: set[tuple[str, str, str | None]] = set()
    for selection in selections:
        if selection.selection_type not in {"item_group", "item_name"}:
            raise Class2OfflineExportError("selection_type must be item_group or item_name")
        label = _normalize_label(selection.label)
        parent = _normalize_label(selection.parent_item_group_label)
        if label is None:
            raise Class2OfflineExportError("selection label is required")
        if selection.selection_type == "item_group" and parent is not None:
            raise Class2OfflineExportError("item_group selection cannot have a parent")
        if selection.selection_type == "item_name" and parent is None:
            raise Class2OfflineExportError("item_name selection requires parent_item_group_label")
        key = (selection.selection_type, label, parent)
        if key not in seen:
            seen.add(key)
            result.append(selection)
    return tuple(result)


def _available_months(parquet_root: Path, requested: tuple[str, ...]) -> tuple[str, ...]:
    available: list[str] = []
    for month in requested:
        try:
            read_monthly_fact_partitions(parquet_root, months=(month,), columns=("month",))
        except InvalidPartitionRequestError:
            continue
        available.append(month)
    return tuple(available)


def _filter_fact(fact: pd.DataFrame, selections: tuple[Class2SelectionRequest, ...]) -> pd.DataFrame:
    if not selections:
        return empty_monthly_fact()
    groups = fact["item_group_id"].map(_normalize_label)
    names = fact["item_name_id"].map(_normalize_label)
    selected = pd.Series(False, index=fact.index, dtype="boolean")
    for request in selections:
        label = _normalize_label(request.label)
        if request.selection_type == "item_group":
            selected |= groups.eq(label).fillna(False)
        else:
            parent = _normalize_label(request.parent_item_group_label)
            parent_matches = groups.isna() if parent is None else groups.eq(parent).fillna(False)
            selected |= names.eq(label).fillna(False) & parent_matches
    return fact.loc[selected.fillna(False)].copy().reset_index(drop=True)


def _requested_selection_ids(
    catalog: pd.DataFrame, selections: tuple[Class2SelectionRequest, ...],
) -> set[str]:
    selected: set[str] = set()
    for request in selections:
        label = _normalize_label(request.label)
        candidates = catalog.loc[
            catalog["selection_type"].eq(request.selection_type)
            & catalog["normalized_label"].eq(label)
        ]
        if request.selection_type == "item_name":
            parent = _normalize_label(request.parent_item_group_label)
            parents = candidates["parent_item_group_label"].map(_normalize_label)
            candidates = candidates.loc[parents.isna() if parent is None else parents.eq(parent)]
        selected.update(candidates["selection_id"].astype(str))
    return selected


def _filter_analysis(tables: Class2AnalysisTables, selection_ids: set[str]) -> Class2AnalysisTables:
    def selected(frame: pd.DataFrame) -> pd.DataFrame:
        return frame.loc[frame["selection_id"].astype(str).isin(selection_ids)].copy().reset_index(drop=True)

    return Class2AnalysisTables(
        selected(tables.selection_catalog),
        selected(tables.selection_month_metrics),
        selected(tables.selection_month_composition),
        selected(tables.selection_coverage_summary),
    )


def _mark_coverage(payload: dict[str, Any]) -> str:
    summaries = payload["selection_coverage_summary"]
    if not summaries:
        return "not_available"
    insufficient = False
    for summary in summaries:
        if summary["missing_month_count"] > 0 or summary["included_month_count"] == 0:
            insufficient = True
            flags = {flag for flag in summary["quality_flags"].split(";") if flag}
            flags.add("local_export_coverage_insufficient")
            summary["quality_flags"] = ";".join(sorted(flags))
    return "insufficient_coverage" if insufficient else "available"


def _empty_payload() -> dict[str, Any]:
    tables = build_class2_analysis(
        empty_monthly_fact(), period_start="200001", period_end="200001", data_version="unavailable"
    )
    return serialize_class2_analysis(tables)


def _local_metadata(state: str, reason: str | None) -> dict[str, Any]:
    return {
        "state": state,
        "reason": reason,
        "publication_scope": "local_only",
        "public_policy_state": "not_applied",
        "suppression_policy_state": "not_evaluated",
    }


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise Class2OfflineExportError(f"could not atomically publish {path.name}") from exc


def _existing_result(
    payload_path: Path, manifest_path: Path, export_fingerprint: str, candidate_payload_sha: str,
) -> Class2OfflineExportResult | Literal["recover_manifest_only"] | None:
    payload_exists = payload_path.exists()
    manifest_exists = manifest_path.exists()
    if not payload_exists and not manifest_exists:
        return None
    if not payload_exists and manifest_exists:
        raise Class2OfflineExportConflictError("existing local export is incomplete; refusing overwrite")
    try:
        payload_sha = sha256(payload_path.read_bytes()).hexdigest()
        if payload_exists and not manifest_exists:
            if payload_sha == candidate_payload_sha:
                return "recover_manifest_only"
            raise Class2OfflineExportConflictError("existing incomplete payload differs from candidate; refusing overwrite")
        raw_manifest = manifest_path.read_bytes()
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Class2OfflineExportConflictError("existing local export is unreadable; refusing overwrite") from exc
    if raw_manifest != _canonical_json_bytes(manifest):
        raise Class2OfflineExportConflictError("existing local export manifest is not canonical; refusing overwrite")
    if manifest.get("payload_sha256") != payload_sha:
        raise Class2OfflineExportConflictError("existing local export checksum disagrees with manifest")
    if manifest.get("export_fingerprint") != export_fingerprint:
        raise Class2OfflineExportConflictError("existing local export has different lineage or selection; refusing overwrite")
    return Class2OfflineExportResult("unchanged", payload_path, manifest_path, payload_sha, str(manifest["export_state"]))


def export_class2_analysis(
    *,
    parquet_root: Path,
    period_start: str,
    period_end: str,
    selections: Iterable[Class2SelectionRequest],
    web_public_root: Path = DEFAULT_WEB_PUBLIC_ROOT,
    availability_state: Literal["available", "suppressed", "not_available"] = "available",
) -> Class2OfflineExportResult:
    """Build and atomically publish the existing local-adapter JSON contract.

    ``web_public_root`` is injectable only for synthetic tests; normal use keeps
    the generated artifact under ``web/class2_public/public/generated``.
    """
    if availability_state not in _STATES:
        raise Class2OfflineExportError("availability_state is invalid")
    requested_months = _months(period_start, period_end)
    normalized_selections = _validate_selections(selections)
    output_dir = Path(web_public_root) / "generated"
    payload_path = output_dir / PAYLOAD_FILENAME
    manifest_path = output_dir / MANIFEST_FILENAME

    verifications: tuple[PartitionVerification, ...] = ()
    source_versions: tuple[str, ...] = ()
    reason: str | None = None
    if availability_state == "suppressed":
        export_state = "suppressed"
        reason = "suppression_state_supplied_by_offline_operator"
        payload = _empty_payload()
    elif availability_state == "not_available" or not normalized_selections:
        export_state = "not_available"
        reason = "selection_required" if not normalized_selections else "not_available_state_supplied_by_offline_operator"
        payload = _empty_payload()
    else:
        available_months = _available_months(Path(parquet_root), requested_months)
        verifications = tuple(verify_monthly_fact_partition(Path(parquet_root), month) for month in available_months)
        if not available_months:
            export_state = "not_available"
            reason = "no_requested_month_partitions"
            payload = _empty_payload()
        else:
            fact = read_monthly_fact_partitions(Path(parquet_root), months=available_months)
            source_versions = tuple(sorted(fact["source_version"].dropna().astype(str).unique()))
            selected_fact = _filter_fact(fact, normalized_selections)
            if selected_fact.empty:
                export_state = "not_available"
                reason = "no_rows_for_requested_selections"
                payload = _empty_payload()
            else:
                data_version = _fingerprint({
                    "partition_lineage": [verification.__dict__ for verification in verifications],
                    "requested_months": requested_months,
                })
                tables = build_class2_analysis(
                    selected_fact, period_start=period_start, period_end=period_end, data_version=data_version,
                )
                selection_ids = _requested_selection_ids(tables.selection_catalog, normalized_selections)
                payload = serialize_class2_analysis(_filter_analysis(tables, selection_ids))
                export_state = _mark_coverage(payload)
                reason = "missing_requested_month_partitions" if export_state == "insufficient_coverage" else None
    payload["local_export"] = _local_metadata(export_state, reason)
    payload_bytes = _canonical_json_bytes(payload)
    payload_sha = sha256(payload_bytes).hexdigest()
    lineage = [
        {
            "month": item.month,
            "row_count": item.row_count,
            "relative_parquet_path": item.relative_parquet_path,
            "parquet_sha256": item.parquet_sha256,
            "parquet_file_size": item.parquet_file_size,
        }
        for item in verifications
    ]
    export_input = {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "period_start": period_start,
        "period_end": period_end,
        "requested_months": requested_months,
        "selections": [request.__dict__ for request in normalized_selections],
        "availability_state": availability_state,
        "lineage": lineage,
        "source_versions": source_versions,
        "analysis_schema_version": CLASS2_ANALYSIS_SCHEMA_VERSION,
        "fact_schema_version": FACT_SCHEMA_VERSION,
        "payload_sha256": payload_sha,
    }
    export_fingerprint = _fingerprint(export_input)
    existing = _existing_result(payload_path, manifest_path, export_fingerprint, payload_sha)
    if isinstance(existing, Class2OfflineExportResult):
        return existing
    manifest = {
        **export_input,
        "export_fingerprint": export_fingerprint,
        "export_state": export_state,
        "local_only": True,
        "public_policy_state": "not_applied",
        "suppression_policy_state": "not_evaluated",
        "payload_filename": PAYLOAD_FILENAME,
    }
    if existing != "recover_manifest_only":
        _atomic_write(payload_path, payload_bytes)
    _atomic_write(manifest_path, _canonical_json_bytes(manifest))
    status: Literal["written", "recovered"] = (
        "recovered" if existing == "recover_manifest_only" else "written"
    )
    return Class2OfflineExportResult(status, payload_path, manifest_path, payload_sha, export_state)


def _read_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Class2OfflineExportError("config must be readable UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise Class2OfflineExportError("config root must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export local-only Class 2 analysis JSON.")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    config = _read_config(args.config)
    selections = tuple(Class2SelectionRequest(**item) for item in config.get("selections", []))
    result = export_class2_analysis(
        parquet_root=Path(config["parquet_root"]),
        period_start=config["period_start"], period_end=config["period_end"],
        selections=selections,
        web_public_root=Path(config.get("web_public_root", DEFAULT_WEB_PUBLIC_ROOT)),
        availability_state=config.get("availability_state", "available"),
    )
    print(_canonical_json_bytes({
        "status": result.status, "output_path": result.output_path.as_posix(),
        "manifest_path": result.manifest_path.as_posix(), "payload_sha256": result.payload_sha256,
        "export_state": result.export_state,
    }).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
