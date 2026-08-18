"""Publish a license-ID to Korean display-name directory from the Excel stream.

Names are captured in the same supply-workbook pass that emits source rows.
They are never identifiers, never GAD-NR features, and never monthly-fact
columns.  Site ingest should write this directory from that one stream.  The
standalone builder is only a catch-up for already-published facts.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import secrets
import shutil
from typing import Any, Final, Literal, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from data_pipeline.ingest.nids_supply_excel import (
    ADAPTER_CONTRACT_VERSION,
    SourceLineage,
    SupplyWorkbookNameError,
    create_source_lineage,
    declared_month_from_logical_names,
    stream_nids_supply_excel,
)


DATASET_NAME: Final = "company_display_name"
SCHEMA_VERSION: Final = "1.1.0"
MANIFEST_FILENAME: Final = "_manifest.json"
PARQUET_FILENAME: Final = "names.parquet"
DISPLAY_NAME_SCHEMA: Final = pa.schema(
    [
        pa.field("entity_id", pa.string()),
        pa.field("display_name", pa.string()),
        pa.field("observation_count", pa.int64()),
        pa.field("distinct_name_count", pa.int64()),
        pa.field("name_conflict", pa.bool_()),
    ]
)


class CompanyDisplayNameError(RuntimeError):
    """Raised when a display-name directory cannot be published safely."""


class CompanyDisplayNameConflictError(CompanyDisplayNameError):
    """Raised rather than replacing an existing directory with different content."""


@dataclass(frozen=True)
class CompanyDisplayNameResult:
    status: Literal["written", "unchanged"]
    output_path: Path
    manifest_path: Path
    created_fingerprint: str
    entity_count: int
    conflict_count: int


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return sha256(_canonical_json_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def directory_path(root: Path) -> Path:
    return Path(root) / DATASET_NAME / f"schema_version={SCHEMA_VERSION}"


def _new_staging_dir(final_dir: Path) -> Path:
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        candidate = final_dir.parent / f".{final_dir.name}.tmp-{secrets.token_hex(8)}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise CompanyDisplayNameError("could not allocate display-name staging directory")


def _rows_frame(rows: Sequence[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(
        list(rows),
        columns=[
            "entity_id",
            "display_name",
            "observation_count",
            "distinct_name_count",
            "name_conflict",
        ],
    )
    if frame.empty:
        frame = pd.DataFrame(
            {
                "entity_id": pd.Series(dtype="string"),
                "display_name": pd.Series(dtype="string"),
                "observation_count": pd.Series(dtype="int64"),
                "distinct_name_count": pd.Series(dtype="int64"),
                "name_conflict": pd.Series(dtype="bool"),
            }
        )
        return frame
    frame["entity_id"] = frame["entity_id"].astype("string")
    frame["display_name"] = frame["display_name"].astype("string")
    frame["observation_count"] = frame["observation_count"].astype("int64")
    frame["distinct_name_count"] = frame["distinct_name_count"].astype("int64")
    frame["name_conflict"] = frame["name_conflict"].astype("bool")
    return frame.sort_values("entity_id", kind="stable").reset_index(drop=True)


def _month_dir_name(month: str) -> str:
    return f"month={month}"


def _write_names_parquet(path: Path, frame: pd.DataFrame) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(frame, schema=DISPLAY_NAME_SCHEMA, preserve_index=False)
    pq.write_table(table, path, compression="zstd")
    return _sha256_file(path)


def _read_names_parquet(path: Path) -> pd.DataFrame:
    return pq.read_table(path, schema=DISPLAY_NAME_SCHEMA).to_pandas()


def _merge_month_frames(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Keep the earliest logical month's name; later disagreements set name_conflict."""
    winners: dict[str, dict[str, Any]] = {}
    seen_names: dict[str, set[str]] = {}
    for month in sorted(frames):
        frame = frames[month]
        for row in frame.itertuples(index=False):
            entity_id = str(row.entity_id)
            display_name = None if pd.isna(row.display_name) else str(row.display_name)
            seen_names.setdefault(entity_id, set())
            if display_name:
                seen_names[entity_id].add(display_name)
            if entity_id not in winners:
                winners[entity_id] = {
                    "entity_id": entity_id,
                    "display_name": display_name,
                    "observation_count": int(row.observation_count),
                    "distinct_name_count": int(row.distinct_name_count),
                    "name_conflict": bool(row.name_conflict),
                }
                continue
            winners[entity_id]["observation_count"] += int(row.observation_count)
            if bool(row.name_conflict):
                winners[entity_id]["name_conflict"] = True
    for entity_id, names in seen_names.items():
        if len(names) > 1:
            winners[entity_id]["name_conflict"] = True
        winners[entity_id]["distinct_name_count"] = max(
            int(winners[entity_id]["distinct_name_count"]),
            len(names),
        )
    return _rows_frame(list(winners.values()))


def _source_month_entry(
    *,
    month: str,
    lineage: SourceLineage,
    names_sha256: str,
    entity_count: int,
) -> dict[str, Any]:
    return {
        "month": month,
        "source_version": lineage.source_version,
        "workbooks": lineage.canonical_payload()["workbooks"],
        "names_sha256": names_sha256,
        "entity_count": entity_count,
    }


def _candidate_manifest(
    *,
    source_months: list[dict[str, Any]],
    parquet_sha256: str,
    entity_count: int,
    conflict_count: int,
) -> dict[str, Any]:
    fingerprint_input = {
        "dataset_name": DATASET_NAME,
        "schema_version": SCHEMA_VERSION,
        "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
        "source_months": source_months,
        "output_sha256": {"names": parquet_sha256},
        "entity_count": entity_count,
        "conflict_count": conflict_count,
        "names_are_not_identifiers": True,
        "first_name_order": "logical_month_ascending",
    }
    return {
        **fingerprint_input,
        "created_fingerprint": _fingerprint(fingerprint_input),
        "scope": "local_internal_only",
        "public_policy_state": "not_applied",
    }


def _existing_matches(final_dir: Path, candidate: dict[str, Any]) -> bool:
    path = final_dir / MANIFEST_FILENAME
    if not path.is_file():
        return False
    try:
        raw = path.read_bytes()
        existing = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompanyDisplayNameConflictError(
            "existing display-name manifest is unreadable"
        ) from exc
    if not isinstance(existing, dict) or raw != _canonical_json_bytes(existing):
        raise CompanyDisplayNameConflictError(
            "existing display-name manifest is not canonical"
        )
    if existing.get("created_fingerprint") != candidate["created_fingerprint"] or existing != candidate:
        return False
    parquet_path = final_dir / PARQUET_FILENAME
    return parquet_path.is_file() and _sha256_file(parquet_path) == candidate["output_sha256"]["names"]


def _load_existing_month_frames(final_dir: Path, manifest: dict[str, Any]) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for entry in manifest.get("source_months") or ():
        month = str(entry["month"])
        path = final_dir / _month_dir_name(month) / PARQUET_FILENAME
        if not path.is_file() or _sha256_file(path) != entry.get("names_sha256"):
            raise CompanyDisplayNameConflictError(
                "existing display-name month partition checksum is invalid"
            )
        frames[month] = _read_names_parquet(path)
    return frames


def write_company_display_name_directory(
    *,
    output_root: Path,
    rows: Sequence[dict[str, Any]],
    lineage: SourceLineage,
    month: str | None = None,
) -> CompanyDisplayNameResult:
    """Atomically publish or merge one logical month of display names."""
    if not isinstance(output_root, Path):
        raise TypeError("output_root must be pathlib.Path")
    if lineage.adapter_contract_version != ADAPTER_CONTRACT_VERSION:
        raise CompanyDisplayNameError("display-name directory requires the current ingest adapter")
    try:
        declared_month = month or declared_month_from_logical_names(
            tuple(item.logical_name for item in lineage.workbooks)
        )
    except SupplyWorkbookNameError as exc:
        raise CompanyDisplayNameError("display-name month must come from dekade filenames") from exc
    month_frame = _rows_frame(rows)
    final_dir = directory_path(output_root)
    existing_manifest: dict[str, Any] | None = None
    existing_frames: dict[str, pd.DataFrame] = {}
    if final_dir.exists():
        loaded = read_company_display_name_directory(output_root)
        if loaded is None:
            raise CompanyDisplayNameConflictError("existing display-name directory is incomplete")
        existing_manifest, _merged = loaded
        existing_frames = _load_existing_month_frames(final_dir, existing_manifest)
        if declared_month in existing_frames:
            staging_probe = _new_staging_dir(final_dir)
            try:
                probe_hash = _write_names_parquet(
                    staging_probe / PARQUET_FILENAME, month_frame
                )
            finally:
                shutil.rmtree(staging_probe, ignore_errors=True)
            existing_entry = next(
                item for item in existing_manifest["source_months"] if item["month"] == declared_month
            )
            if existing_entry.get("names_sha256") != probe_hash:
                raise CompanyDisplayNameConflictError(
                    "existing display-name month has different content; refusing overwrite"
                )
            return CompanyDisplayNameResult(
                "unchanged",
                final_dir,
                final_dir / MANIFEST_FILENAME,
                str(existing_manifest["created_fingerprint"]),
                int(existing_manifest["entity_count"]),
                int(existing_manifest["conflict_count"]),
            )
    frames = {**existing_frames, declared_month: month_frame}
    merged = _merge_month_frames(frames)
    staging = _new_staging_dir(final_dir)
    try:
        for month_key, frame in frames.items():
            dest = staging / _month_dir_name(month_key) / PARQUET_FILENAME
            existing_month_path = final_dir / _month_dir_name(month_key) / PARQUET_FILENAME
            if month_key != declared_month and existing_month_path.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(existing_month_path, dest)
            else:
                _write_names_parquet(dest, frame)
        parquet_sha256 = _write_names_parquet(staging / PARQUET_FILENAME, merged)
        source_months = []
        if existing_manifest is not None:
            source_months.extend(
                item for item in existing_manifest["source_months"] if item["month"] != declared_month
            )
        source_months.append(
            _source_month_entry(
                month=declared_month,
                lineage=lineage,
                names_sha256=_sha256_file(staging / _month_dir_name(declared_month) / PARQUET_FILENAME),
                entity_count=int(len(month_frame)),
            )
        )
        source_months.sort(key=lambda item: str(item["month"]))
        candidate = _candidate_manifest(
            source_months=source_months,
            parquet_sha256=parquet_sha256,
            entity_count=int(len(merged)),
            conflict_count=int(merged["name_conflict"].sum()) if len(merged) else 0,
        )
        (staging / MANIFEST_FILENAME).write_bytes(_canonical_json_bytes(candidate))
        if final_dir.exists():
            if _existing_matches(final_dir, candidate):
                shutil.rmtree(staging)
                return CompanyDisplayNameResult(
                    "unchanged",
                    final_dir,
                    final_dir / MANIFEST_FILENAME,
                    candidate["created_fingerprint"],
                    candidate["entity_count"],
                    candidate["conflict_count"],
                )
            shutil.rmtree(final_dir)
        staging.replace(final_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return CompanyDisplayNameResult(
        "written",
        final_dir,
        final_dir / MANIFEST_FILENAME,
        candidate["created_fingerprint"],
        candidate["entity_count"],
        candidate["conflict_count"],
    )


def read_company_display_name_directory(root: Path) -> tuple[dict[str, Any], pd.DataFrame] | None:
    """Return the verified directory, or None when it has not been published."""
    directory = directory_path(Path(root))
    manifest_path = directory / MANIFEST_FILENAME
    parquet_path = directory / PARQUET_FILENAME
    if not manifest_path.is_file():
        return None
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompanyDisplayNameError("display-name manifest is unreadable") from exc
    if not isinstance(manifest, dict) or raw != _canonical_json_bytes(manifest):
        raise CompanyDisplayNameError("display-name manifest is not canonical")
    if manifest.get("dataset_name") != DATASET_NAME or manifest.get("schema_version") != SCHEMA_VERSION:
        raise CompanyDisplayNameError("display-name directory schema is unsupported")
    if manifest.get("names_are_not_identifiers") is not True:
        raise CompanyDisplayNameError("display-name directory must not treat names as identifiers")
    if not parquet_path.is_file() or _sha256_file(parquet_path) != manifest.get("output_sha256", {}).get("names"):
        raise CompanyDisplayNameError("display-name parquet checksum is invalid")
    frame = pq.read_table(parquet_path, schema=DISPLAY_NAME_SCHEMA).to_pandas()
    if int(len(frame)) != int(manifest["entity_count"]):
        raise CompanyDisplayNameError("display-name row count does not match the manifest")
    return manifest, frame


def build_company_display_name_directory(
    *,
    supply_paths: Sequence[Path],
    output_root: Path,
    batch_size: int = 10_000,
) -> CompanyDisplayNameResult:
    """Catch-up builder: stream workbooks once and publish names without rebuilding facts."""
    paths = tuple(Path(path) for path in supply_paths)
    lineage = create_source_lineage(paths)
    with stream_nids_supply_excel(paths, batch_size=batch_size) as stream:
        if stream.lineage != lineage:
            raise CompanyDisplayNameError("Supply lineage changed between snapshot and streaming")
        for _batch in stream:
            pass
        rows = stream.display_name_rows()
    return write_company_display_name_directory(
        output_root=output_root, rows=rows, lineage=lineage
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a Korean company display-name directory from supply Excel."
    )
    parser.add_argument("--supply-workbooks", required=True, nargs="+", type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=10_000)
    args = parser.parse_args(argv)
    try:
        result = build_company_display_name_directory(
            supply_paths=args.supply_workbooks,
            output_root=args.output_root,
            batch_size=args.batch_size,
        )
    except CompanyDisplayNameError as exc:
        print(_canonical_json_bytes({"error": type(exc).__name__, "message": str(exc)}).decode("utf-8"))
        return 2
    print(
        _canonical_json_bytes(
            {
                "status": result.status,
                "created_fingerprint": result.created_fingerprint,
                "entity_count": result.entity_count,
                "conflict_count": result.conflict_count,
            }
        ).decode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
