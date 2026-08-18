"""End-to-end offline supply-month orchestration using existing public APIs."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import secrets
from typing import Any, Final, Sequence

import numpy as np
import pandas as pd

from data_pipeline.checkpoints import (
    CheckpointIntegrityError,
    CheckpointSealedError,
    SealedCheckpointResult,
    SupplyMonthlyCheckpoint,
    create_or_open_supply_monthly_checkpoint,
    derive_supply_monthly_run_id,
    finalize_sealed_supply_checkpoint,
    read_sealed_month_fact,
    verify_sealed_supply_checkpoint,
)
from data_pipeline.checkpoints.supply_monthly import (
    CHECKPOINT_CONTRACT_VERSION,
    DATASET_NAME as CHECKPOINT_DATASET_NAME,
    SEALED_MANIFEST_FILENAME,
)
from data_pipeline.contracts import FACT_SCHEMA_VERSION
from data_pipeline.ingest import (
    SourceLineage,
    create_source_lineage,
    stream_nids_supply_excel,
)
from data_pipeline.ingest.company_display_name import (
    CompanyDisplayNameError,
    write_company_display_name_directory,
)
from data_pipeline.storage import (
    MasterLookupVerification,
    open_master_product_lookup,
    verify_master_product_lookup,
    verify_monthly_fact_partition,
    write_monthly_fact_partitions,
)
from data_pipeline.storage.monthly_fact_parquet import (
    DATASET_NAME as MONTHLY_FACT_DATASET_NAME,
    MANIFEST_FILENAME as PARTITION_MANIFEST_FILENAME,
    STORAGE_CONTRACT_VERSION,
)


COMPLETE_MANIFEST_FILENAME: Final = "_complete_manifest.json"
COMPLETE_CONTRACT_VERSION: Final = "1.0.0"
_HEX_LENGTH: Final = 64


class SupplyMonthlyOrchestrationError(RuntimeError):
    """Base error for the PR-03B2B orchestration contract."""


class UnsafeOrchestrationPathError(SupplyMonthlyOrchestrationError):
    """Raised when checkpoint and service-data roots overlap."""


class OrchestrationIntegrityError(SupplyMonthlyOrchestrationError):
    """Raised when cross-stage accounting or an artifact is inconsistent."""


class CompleteManifestConflictError(SupplyMonthlyOrchestrationError):
    """Raised when an existing complete manifest differs or is damaged."""


@dataclass(frozen=True)
class OrchestrationResult:
    status: str
    run_id: str
    written_months: tuple[str, ...]
    unchanged_months: tuple[str, ...]
    skipped_unmatched_only_months: tuple[str, ...]
    relative_complete_manifest_path: str


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_file(path: Path, *, label: str) -> str:
    digest = sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise OrchestrationIntegrityError(f"Could not checksum {label}") from exc
    return digest.hexdigest()


def _require_path(value: Path, name: str) -> Path:
    if not isinstance(value, Path):
        raise TypeError(f"{name} must be pathlib.Path")
    return value


def _validate_disjoint_roots(checkpoint_root: Path, output_root: Path) -> None:
    checkpoint = os.path.normcase(str(checkpoint_root.resolve(strict=False)))
    output = os.path.normcase(str(output_root.resolve(strict=False)))
    try:
        common = os.path.commonpath((checkpoint, output))
    except ValueError:
        return
    if common in {checkpoint, output}:
        raise UnsafeOrchestrationPathError(
            "checkpoint_root and output_root must be distinct non-nested paths"
        )


def _run_dir(checkpoint_root: Path, run_id: str) -> Path:
    return (
        checkpoint_root
        / CHECKPOINT_DATASET_NAME
        / f"checkpoint_version={CHECKPOINT_CONTRACT_VERSION}"
        / f"run_id={run_id}"
    )


def _relative_complete_manifest_path(run_id: str) -> str:
    return PurePosixPath(
        CHECKPOINT_DATASET_NAME,
        f"checkpoint_version={CHECKPOINT_CONTRACT_VERSION}",
        f"run_id={run_id}",
        COMPLETE_MANIFEST_FILENAME,
    ).as_posix()


def _read_canonical_manifest(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompleteManifestConflictError(
            "Complete manifest is missing, unreadable, or invalid"
        ) from exc
    if not isinstance(value, dict) or raw != _canonical_json_bytes(value):
        raise CompleteManifestConflictError("Complete manifest is not canonical JSON")
    return value


def _publish_complete_manifest(path: Path, manifest: dict[str, Any]) -> bool:
    """Atomically create an immutable manifest; return False for identical state."""

    payload = _canonical_json_bytes(manifest)
    if path.exists():
        if _read_canonical_manifest(path) != manifest:
            raise CompleteManifestConflictError(
                "Existing complete manifest has different content"
            )
        return False
    candidate = path.with_name(f".{path.name}.tmp-{secrets.token_hex(6)}")
    try:
        candidate.write_bytes(payload)
        try:
            os.link(candidate, path)
        except FileExistsError:
            if _read_canonical_manifest(path) != manifest:
                raise CompleteManifestConflictError(
                    "Competing complete manifest has different content"
                )
            return False
        except OSError as exc:
            if path.exists():
                if _read_canonical_manifest(path) != manifest:
                    raise CompleteManifestConflictError(
                        "Competing complete manifest has different content"
                    ) from exc
                return False
            raise SupplyMonthlyOrchestrationError(
                "Could not publish complete manifest atomically"
            ) from exc
        return True
    except OSError as exc:
        raise SupplyMonthlyOrchestrationError(
            "Could not write complete manifest candidate"
        ) from exc
    finally:
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass


def _partition_manifest_path(output_root: Path, relative_parquet_path: str) -> Path:
    relative = PurePosixPath(relative_parquet_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise OrchestrationIntegrityError("PR-02 relative Parquet path is unsafe")
    return output_root.joinpath(*relative.parent.parts, PARTITION_MANIFEST_FILENAME)


def _complete_manifest(
    *,
    run_id: str,
    sealed_manifest_sha256: str,
    published_months: list[dict[str, Any]],
    skipped_months: list[str],
) -> dict[str, Any]:
    payload = {
        "checkpoint_contract_version": CHECKPOINT_CONTRACT_VERSION,
        "complete_contract_version": COMPLETE_CONTRACT_VERSION,
        "fact_schema_version": FACT_SCHEMA_VERSION,
        "published_months": published_months,
        "run_id": run_id,
        "sealed_manifest_sha256": sealed_manifest_sha256,
        "skipped_unmatched_only_months": skipped_months,
        "storage_contract_version": STORAGE_CONTRACT_VERSION,
    }
    return {
        **payload,
        "complete_payload_fingerprint": sha256(
            _canonical_json_bytes(payload)
        ).hexdigest(),
    }


def _validate_complete_manifest_shape(manifest: dict[str, Any]) -> None:
    expected = {
        "checkpoint_contract_version",
        "complete_contract_version",
        "complete_payload_fingerprint",
        "fact_schema_version",
        "published_months",
        "run_id",
        "sealed_manifest_sha256",
        "skipped_unmatched_only_months",
        "storage_contract_version",
    }
    if set(manifest) != expected:
        raise CompleteManifestConflictError("Complete manifest field set is invalid")
    fingerprint = manifest.get("complete_payload_fingerprint")
    payload = {key: value for key, value in manifest.items() if key != "complete_payload_fingerprint"}
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != _HEX_LENGTH
        or fingerprint != sha256(_canonical_json_bytes(payload)).hexdigest()
    ):
        raise CompleteManifestConflictError("Complete manifest fingerprint is invalid")


def _open_or_recover_checkpoint(
    *,
    checkpoint_root: Path,
    run_id: str,
    supply_lineage: SourceLineage,
    master_verification: MasterLookupVerification,
) -> tuple[SealedCheckpointResult | None, SupplyMonthlyCheckpoint | None]:
    run_dir = _run_dir(checkpoint_root, run_id)
    if (run_dir / SEALED_MANIFEST_FILENAME).is_file():
        return verify_sealed_supply_checkpoint(checkpoint_root, run_id), None
    try:
        checkpoint = create_or_open_supply_monthly_checkpoint(
            checkpoint_root,
            supply_lineage=supply_lineage,
            master_verification=master_verification,
        )
    except CheckpointIntegrityError as open_error:
        try:
            return finalize_sealed_supply_checkpoint(checkpoint_root, run_id), None
        except CheckpointIntegrityError:
            raise open_error
    except CheckpointSealedError:
        return verify_sealed_supply_checkpoint(checkpoint_root, run_id), None
    return None, checkpoint


def _seal_active_checkpoint(
    *,
    checkpoint: SupplyMonthlyCheckpoint,
    supply_paths: Sequence[Path],
    supply_lineage: SourceLineage,
    master_lookup_root: Path,
    master_source_hash: str,
    batch_size: int,
    max_month_fact_bytes: int,
    output_root: Path,
) -> SealedCheckpointResult:
    with checkpoint:
        with stream_nids_supply_excel(
            supply_paths, batch_size=batch_size
        ) as stream, open_master_product_lookup(
            master_lookup_root, master_source_hash
        ) as lookup:
            if stream.lineage != supply_lineage:
                raise OrchestrationIntegrityError(
                    "Supply lineage changed between snapshot and streaming"
                )
            for batch in stream:
                normalized_batch = batch.reset_index(drop=True)
                if not isinstance(normalized_batch.index, pd.RangeIndex):
                    # This branch is defensive; reset_index should always create RangeIndex.
                    raise OrchestrationIntegrityError("Supply batch index reset failed")
                joined = lookup.join_supply_batch(normalized_batch)
                report = joined.report
                if report.rows_input != len(normalized_batch):
                    raise OrchestrationIntegrityError("Master join input count differs")
                if report.rows_matched + report.rows_unmatched != len(normalized_batch):
                    raise OrchestrationIntegrityError("Master join accounting differs")
                matched_positions = joined.matched_rows.index.to_numpy(dtype=np.int64)
                if (
                    len(matched_positions) != report.rows_matched
                    or len(set(matched_positions.tolist())) != len(matched_positions)
                    or any(position < 0 or position >= len(normalized_batch) for position in matched_positions)
                ):
                    raise OrchestrationIntegrityError("Master join matched positions are invalid")
                matched_mask = np.zeros(len(normalized_batch), dtype=bool)
                matched_mask[matched_positions] = True
                if int(matched_mask.sum()) != report.rows_matched:
                    raise OrchestrationIntegrityError("Master join report and mask differ")
                checkpoint.apply_classified_batch(
                    normalized_batch, matched_mask=matched_mask
                )
            stream.report.validate_accounting()
            name_rows = stream.display_name_rows()
            sealed = checkpoint.seal(
                adapter_report=stream.report,
                max_fact_bytes=max_month_fact_bytes,
            )
    try:
        write_company_display_name_directory(
            output_root=output_root,
            rows=name_rows,
            lineage=supply_lineage,
        )
    except CompanyDisplayNameError as exc:
        raise OrchestrationIntegrityError(
            f"Could not publish company display-name directory from the ingest pass: {exc}"
        ) from exc
    return sealed


def _publish_or_verify_months(
    *,
    sealed: SealedCheckpointResult,
    checkpoint_root: Path,
    output_root: Path,
    max_month_fact_bytes: int,
    verify_only: bool,
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    fingerprints = dict(sealed.fact_fingerprints)
    entries: list[dict[str, Any]] = []
    skipped: list[str] = []
    written: list[str] = []
    unchanged: list[str] = []
    for month in sealed.months:
        fact = read_sealed_month_fact(
            checkpoint_root,
            sealed.run_id,
            month,
            max_fact_bytes=max_month_fact_bytes,
        )
        if fact.empty:
            unexpected_partition = (
                output_root
                / MONTHLY_FACT_DATASET_NAME
                / f"schema_version={FACT_SCHEMA_VERSION}"
                / f"month={month}"
            )
            if unexpected_partition.exists():
                raise OrchestrationIntegrityError(
                    f"Unmatched-only month {month} has an unexpected partition"
                )
            skipped.append(month)
            continue
        if verify_only:
            verification = verify_monthly_fact_partition(output_root, month)
            unchanged.append(month)
        else:
            write_result = write_monthly_fact_partitions(fact, output_root)
            if write_result.partition_count != 1:
                raise OrchestrationIntegrityError(
                    f"PR-02 writer did not return exactly one partition for {month}"
                )
            written.extend(write_result.written_months)
            unchanged.extend(write_result.unchanged_months)
            verification = verify_monthly_fact_partition(output_root, month)
        if verification.row_count != len(fact):
            raise OrchestrationIntegrityError(
                f"Published partition {month} row count differs from sealed fact"
            )
        manifest_path = _partition_manifest_path(
            output_root, verification.relative_parquet_path
        )
        entries.append(
            {
                "fact_fingerprint": fingerprints[month],
                "month": month,
                "parquet_file_size": verification.parquet_file_size,
                "parquet_manifest_sha256": _sha256_file(
                    manifest_path, label=f"PR-02 manifest for {month}"
                ),
                "parquet_sha256": verification.parquet_sha256,
                "relative_parquet_path": verification.relative_parquet_path,
                "row_count": verification.row_count,
            }
        )
    return entries, skipped, written, unchanged


def run_supply_monthly_orchestration(
    *,
    supply_paths: Sequence[Path],
    master_lookup_root: Path,
    master_source_hash: str,
    checkpoint_root: Path,
    output_root: Path,
    max_month_fact_bytes: int,
    batch_size: int = 10_000,
) -> OrchestrationResult:
    """Run or resume the exact-key supply-to-monthly-Parquet pipeline."""

    checkpoint_root = _require_path(checkpoint_root, "checkpoint_root")
    output_root = _require_path(output_root, "output_root")
    master_lookup_root = _require_path(master_lookup_root, "master_lookup_root")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")
    if (
        isinstance(max_month_fact_bytes, bool)
        or not isinstance(max_month_fact_bytes, int)
        or max_month_fact_bytes < 1
    ):
        raise ValueError("max_month_fact_bytes must be a positive integer")
    _validate_disjoint_roots(checkpoint_root, output_root)

    supply_paths = tuple(supply_paths)
    supply_lineage = create_source_lineage(supply_paths)
    master_verification = verify_master_product_lookup(
        master_lookup_root, master_source_hash
    )
    run_id = derive_supply_monthly_run_id(supply_lineage, master_verification)
    run_dir = _run_dir(checkpoint_root, run_id)
    complete_path = run_dir / COMPLETE_MANIFEST_FILENAME
    existing_complete = (
        _read_canonical_manifest(complete_path) if complete_path.exists() else None
    )
    if existing_complete is not None:
        _validate_complete_manifest_shape(existing_complete)

    sealed, active = _open_or_recover_checkpoint(
        checkpoint_root=checkpoint_root,
        run_id=run_id,
        supply_lineage=supply_lineage,
        master_verification=master_verification,
    )
    if sealed is None:
        if existing_complete is not None:
            raise CompleteManifestConflictError(
                "Complete manifest exists for an active checkpoint"
            )
        if active is None:
            raise OrchestrationIntegrityError("Active checkpoint handle is missing")
        sealed = _seal_active_checkpoint(
            checkpoint=active,
            supply_paths=supply_paths,
            supply_lineage=supply_lineage,
            master_lookup_root=master_lookup_root,
            master_source_hash=master_source_hash,
            batch_size=batch_size,
            max_month_fact_bytes=max_month_fact_bytes,
            output_root=output_root,
        )

    entries, skipped, written, unchanged = _publish_or_verify_months(
        sealed=sealed,
        checkpoint_root=checkpoint_root,
        output_root=output_root,
        max_month_fact_bytes=max_month_fact_bytes,
        verify_only=existing_complete is not None,
    )
    sealed_manifest_path = run_dir / SEALED_MANIFEST_FILENAME
    manifest = _complete_manifest(
        run_id=run_id,
        sealed_manifest_sha256=_sha256_file(
            sealed_manifest_path, label="sealed checkpoint manifest"
        ),
        published_months=entries,
        skipped_months=skipped,
    )
    if existing_complete is not None and existing_complete != manifest:
        raise CompleteManifestConflictError(
            "Existing complete manifest differs from verified artifacts"
        )
    created = _publish_complete_manifest(complete_path, manifest)
    return OrchestrationResult(
        status="completed" if created else "unchanged",
        run_id=run_id,
        written_months=tuple(written),
        unchanged_months=tuple(unchanged),
        skipped_unmatched_only_months=tuple(skipped),
        relative_complete_manifest_path=_relative_complete_manifest_path(run_id),
    )
