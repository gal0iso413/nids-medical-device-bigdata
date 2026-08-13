"""Deterministic monthly Parquet storage for the shared supply fact.

This module accepts only a PR-01 monthly fact DataFrame. It performs no raw
source ingestion and has no institution-specific storage path. A month
partition is published by renaming a complete temporary directory, so readers
never treat a partially written pair of Parquet and manifest files as valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from itertools import islice
import json
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
from typing import Any, Final, Iterable, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from data_pipeline.contracts.supply_monthly import (
    FACT_SCHEMA_NAME,
    FACT_SCHEMA_VERSION,
    MONTHLY_FACT_COLUMNS,
    MONTHLY_FACT_SCHEMA,
    empty_monthly_fact,
    validate_monthly_fact,
)


DATASET_NAME: Final = FACT_SCHEMA_NAME
STORAGE_CONTRACT_VERSION: Final = "1.0.0"
PARTITION_COLUMN: Final = "month"
PARQUET_FILENAME: Final = "part-00000.parquet"
MANIFEST_FILENAME: Final = "_manifest.json"
COMPRESSION: Final = "zstd"
DECIMAL_TYPE: Final = pa.decimal128(38, 6)
DECIMAL_COLUMNS: Final[tuple[str, ...]] = (
    "amount_sum_clean",
    "raw_supply_qty_sum",
    "piece_qty_sum",
)
COUNT_COLUMNS: Final[tuple[str, ...]] = (
    "tx_count",
    "amount_valid_row_count",
    "raw_supply_qty_valid_row_count",
    "piece_qty_valid_row_count",
    "unique_udi_count",
    "active_day_count",
)
STRING_COLUMNS: Final[tuple[str, ...]] = tuple(
    column
    for column in MONTHLY_FACT_COLUMNS
    if column not in set(DECIMAL_COLUMNS) | set(COUNT_COLUMNS)
)
GRAIN_COLUMNS: Final[tuple[str, ...]] = (
    "month",
    "src_company_id",
    "dst_company_id",
    "product_id",
)
_MONTH_PATTERN: Final = re.compile(r"^\d{6}$")
_DIAGNOSTIC_LIMIT: Final = 20
_MANIFEST_KEYS: Final[frozenset[str]] = frozenset(
    {
        "dataset_name",
        "logical_schema_name",
        "logical_schema_version",
        "logical_schema_fingerprint",
        "storage_contract_version",
        "partition_column",
        "partition_value",
        "relative_parquet_path",
        "row_count",
        "column_order",
        "source_versions",
        "compression",
        "decimal_encoding",
        "parquet_file_size",
        "parquet_sha256",
    }
)


class MonthlyFactStorageError(RuntimeError):
    """Base error for the monthly fact storage contract."""


class DecimalEncodingError(MonthlyFactStorageError):
    """Raised when a Decimal cannot be represented without loss."""


class PartitionConflictError(MonthlyFactStorageError):
    """Raised when an existing complete month differs from the new input."""


class PartitionIntegrityError(MonthlyFactStorageError):
    """Raised when a stored partition or manifest is incomplete or damaged."""


class InvalidPartitionRequestError(MonthlyFactStorageError):
    """Raised for an unknown month, column, or unsafe request value."""


@dataclass(frozen=True)
class WriteResult:
    """Summary of published and idempotently unchanged month partitions."""

    written_months: tuple[str, ...]
    unchanged_months: tuple[str, ...]
    input_row_count: int

    @property
    def partition_count(self) -> int:
        return len(self.written_months) + len(self.unchanged_months)


@dataclass(frozen=True)
class PartitionVerification:
    """Result of a full manifest, schema, and checksum verification."""

    month: str
    row_count: int
    relative_parquet_path: str
    parquet_sha256: str
    parquet_file_size: int


def monthly_fact_arrow_schema() -> pa.Schema:
    """Return the explicit Arrow physical schema in PR-01 column order."""
    fields: list[pa.Field] = []
    for column in MONTHLY_FACT_COLUMNS:
        if column in DECIMAL_COLUMNS:
            data_type = DECIMAL_TYPE
        elif column in COUNT_COLUMNS:
            data_type = pa.int64()
        else:
            data_type = pa.string()
        fields.append(pa.field(column, data_type, nullable=True))
    return pa.schema(fields)


ARROW_SCHEMA: Final = monthly_fact_arrow_schema()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _logical_schema_fingerprint() -> str:
    payload = {
        "columns": [[column, MONTHLY_FACT_SCHEMA[column]] for column in MONTHLY_FACT_COLUMNS],
        "name": FACT_SCHEMA_NAME,
        "version": FACT_SCHEMA_VERSION,
    }
    return sha256(_canonical_json_bytes(payload)).hexdigest()


LOGICAL_SCHEMA_FINGERPRINT: Final = _logical_schema_fingerprint()
DECIMAL_ENCODING: Final[dict[str, str]] = {
    column: "decimal128(38,6)" for column in DECIMAL_COLUMNS
}


def _require_path(output_root: Path) -> Path:
    if not isinstance(output_root, Path):
        raise TypeError("output_root must be a pathlib.Path")
    return output_root


def _validate_month(month: str) -> str:
    if not isinstance(month, str) or not _MONTH_PATTERN.fullmatch(month):
        raise InvalidPartitionRequestError(
            f"month must be a valid YYYYMM value, got {month!r}"
        )
    try:
        parsed = pd.to_datetime(month, format="%Y%m", errors="raise")
    except (TypeError, ValueError) as exc:
        raise InvalidPartitionRequestError(
            f"month must be a valid YYYYMM value, got {month!r}"
        ) from exc
    if parsed.strftime("%Y%m") != month:
        raise InvalidPartitionRequestError(
            f"month must be a valid YYYYMM value, got {month!r}"
        )
    return month


def _schema_root(output_root: Path) -> Path:
    return (
        output_root
        / DATASET_NAME
        / f"schema_version={FACT_SCHEMA_VERSION}"
    )


def _partition_dir(output_root: Path, month: str) -> Path:
    return _schema_root(output_root) / f"month={_validate_month(month)}"


def _relative_parquet_path(month: str) -> str:
    return str(
        PurePosixPath(
            DATASET_NAME,
            f"schema_version={FACT_SCHEMA_VERSION}",
            f"month={month}",
            PARQUET_FILENAME,
        )
    )


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _decimal_fits(value: Decimal) -> bool:
    if not value.is_finite():
        return False
    sign, digits, exponent = value.as_tuple()
    del sign
    scale = max(-exponent, 0)
    integer_digits = max(len(digits) + exponent, 0)
    return scale <= 6 and integer_digits <= 32


def _validate_decimal_encoding(fact: pd.DataFrame) -> None:
    for column in DECIMAL_COLUMNS:
        invalid = fact[column].map(
            lambda value: False
            if value is None or value is pd.NA or pd.isna(value)
            else not isinstance(value, Decimal) or not _decimal_fits(value)
        )
        if invalid.any():
            sample = list(islice((fact.index[position] for position, flag in enumerate(invalid.array) if flag), _DIAGNOSTIC_LIMIT))
            total = int(invalid.sum())
            raise DecimalEncodingError(
                f"{column!r} exceeds decimal128(38,6) precision/scale or is "
                f"non-finite; total={total}; sample={sample}; "
                f"omitted={max(total - len(sample), 0)}"
            )


def _to_arrow_table(fact: pd.DataFrame) -> pa.Table:
    _validate_decimal_encoding(fact)
    try:
        table = pa.Table.from_pandas(
            fact.loc[:, MONTHLY_FACT_COLUMNS],
            schema=ARROW_SCHEMA,
            preserve_index=False,
            safe=True,
        )
    except (pa.ArrowException, ValueError, TypeError) as exc:
        raise MonthlyFactStorageError(
            "Monthly fact could not be converted to the explicit Arrow schema"
        ) from exc
    return table.replace_schema_metadata(None)


def _write_parquet(table: pa.Table, path: Path) -> None:
    pq.write_table(
        table,
        path,
        compression=COMPRESSION,
        use_dictionary=False,
        write_statistics=True,
        row_group_size=65_536,
        data_page_version="1.0",
    )


def _manifest_for(month: str, fact: pd.DataFrame, parquet_path: Path) -> dict[str, Any]:
    return {
        "column_order": list(MONTHLY_FACT_COLUMNS),
        "compression": COMPRESSION,
        "dataset_name": DATASET_NAME,
        "decimal_encoding": DECIMAL_ENCODING,
        "logical_schema_fingerprint": LOGICAL_SCHEMA_FINGERPRINT,
        "logical_schema_name": FACT_SCHEMA_NAME,
        "logical_schema_version": FACT_SCHEMA_VERSION,
        "parquet_file_size": parquet_path.stat().st_size,
        "parquet_sha256": _sha256_file(parquet_path),
        "partition_column": PARTITION_COLUMN,
        "partition_value": month,
        "relative_parquet_path": _relative_parquet_path(month),
        "row_count": len(fact),
        "source_versions": sorted(fact["source_version"].dropna().unique().tolist()),
        "storage_contract_version": STORAGE_CONTRACT_VERSION,
    }


def _write_candidate(month_fact: pd.DataFrame, month: str, temp_dir: Path) -> dict[str, Any]:
    parquet_path = temp_dir / PARQUET_FILENAME
    manifest_path = temp_dir / MANIFEST_FILENAME
    try:
        _write_parquet(_to_arrow_table(month_fact), parquet_path)
    except (OSError, pa.ArrowException) as exc:
        raise MonthlyFactStorageError(
            f"Could not write temporary Parquet data for partition {month}"
        ) from exc
    manifest = _manifest_for(month, month_fact, parquet_path)
    manifest_path.write_bytes(_canonical_json_bytes(manifest))
    return manifest


def _create_temp_partition_dir(schema_root: Path, month: str) -> Path:
    """Create a private-name staging directory without platform ACL surprises."""
    for _ in range(10):
        candidate = schema_root / f".month={month}.tmp-{secrets.token_hex(8)}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise MonthlyFactStorageError(
        f"Could not allocate a temporary directory for partition {month}"
    )


def _parse_manifest(partition_dir: Path, month: str) -> dict[str, Any]:
    manifest_path = partition_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise PartitionIntegrityError(
            f"Partition {month} is incomplete: {MANIFEST_FILENAME} is missing"
        )
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PartitionIntegrityError(
            f"Partition {month} has an unreadable manifest"
        ) from exc
    if not isinstance(manifest, dict) or frozenset(manifest) != _MANIFEST_KEYS:
        raise PartitionIntegrityError(
            f"Partition {month} manifest fields do not match the storage contract"
        )
    if raw != _canonical_json_bytes(manifest):
        raise PartitionIntegrityError(
            f"Partition {month} manifest is not canonical UTF-8 JSON"
        )
    expected_values = {
        "dataset_name": DATASET_NAME,
        "logical_schema_name": FACT_SCHEMA_NAME,
        "logical_schema_version": FACT_SCHEMA_VERSION,
        "logical_schema_fingerprint": LOGICAL_SCHEMA_FINGERPRINT,
        "storage_contract_version": STORAGE_CONTRACT_VERSION,
        "partition_column": PARTITION_COLUMN,
        "partition_value": month,
        "relative_parquet_path": _relative_parquet_path(month),
        "column_order": list(MONTHLY_FACT_COLUMNS),
        "compression": COMPRESSION,
        "decimal_encoding": DECIMAL_ENCODING,
    }
    for key, expected in expected_values.items():
        if manifest.get(key) != expected:
            raise PartitionIntegrityError(
                f"Partition {month} manifest has invalid {key!r}"
            )
    if (
        not isinstance(manifest.get("row_count"), int)
        or manifest["row_count"] < 0
        or not isinstance(manifest.get("parquet_file_size"), int)
        or manifest["parquet_file_size"] < 0
        or not isinstance(manifest.get("parquet_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", manifest["parquet_sha256"])
    ):
        raise PartitionIntegrityError(
            f"Partition {month} manifest has invalid file metadata"
        )
    source_versions = manifest.get("source_versions")
    if (
        not isinstance(source_versions, list)
        or any(not isinstance(value, str) for value in source_versions)
        or source_versions != sorted(set(source_versions))
    ):
        raise PartitionIntegrityError(
            f"Partition {month} manifest has invalid source_versions"
        )
    return manifest


def _parquet_file(partition_dir: Path, month: str) -> Path:
    parquet_path = partition_dir / PARQUET_FILENAME
    if not parquet_path.is_file():
        raise PartitionIntegrityError(
            f"Partition {month} is incomplete: {PARQUET_FILENAME} is missing"
        )
    return parquet_path


def _validate_arrow_fields(actual: pa.Schema, columns: Sequence[str], month: str) -> None:
    expected = ARROW_SCHEMA
    for column in columns:
        try:
            actual_field = actual.field(column)
        except KeyError as exc:
            raise PartitionIntegrityError(
                f"Partition {month} Parquet schema is missing {column!r}"
            ) from exc
        if actual_field != expected.field(column):
            raise PartitionIntegrityError(
                f"Partition {month} has an invalid Arrow field for {column!r}"
            )


def _inspect_partition_without_checksum(
    output_root: Path,
    month: str,
    *,
    columns: Sequence[str],
) -> tuple[dict[str, Any], Path, pq.ParquetFile]:
    partition_dir = _partition_dir(output_root, month)
    if not partition_dir.is_dir():
        raise InvalidPartitionRequestError(f"Unknown month partition: {month}")
    manifest = _parse_manifest(partition_dir, month)
    parquet_path = _parquet_file(partition_dir, month)
    try:
        parquet_file = pq.ParquetFile(parquet_path)
    except (OSError, pa.ArrowException) as exc:
        raise PartitionIntegrityError(
            f"Partition {month} Parquet metadata is unreadable"
        ) from exc
    _validate_arrow_fields(parquet_file.schema_arrow.remove_metadata(), columns, month)
    if parquet_file.metadata.num_rows != manifest["row_count"]:
        raise PartitionIntegrityError(
            f"Partition {month} row_count does not match the manifest"
        )
    return manifest, parquet_path, parquet_file


def verify_monthly_fact_partition(
    output_root: Path,
    month: str,
) -> PartitionVerification:
    """Verify manifest, full Arrow schema, file size, and SHA-256."""
    root = _require_path(output_root)
    normalized_month = _validate_month(month)
    manifest, parquet_path, parquet_file = _inspect_partition_without_checksum(
        root,
        normalized_month,
        columns=MONTHLY_FACT_COLUMNS,
    )
    actual_schema = parquet_file.schema_arrow.remove_metadata()
    if not actual_schema.equals(ARROW_SCHEMA, check_metadata=False):
        raise PartitionIntegrityError(
            f"Partition {normalized_month} Arrow schema does not match version 1.0.0"
        )
    compressions = {
        parquet_file.metadata.row_group(row_group).column(column).compression
        for row_group in range(parquet_file.metadata.num_row_groups)
        for column in range(parquet_file.metadata.num_columns)
    }
    if compressions != {COMPRESSION.upper()}:
        raise PartitionIntegrityError(
            f"Partition {normalized_month} physical compression is not {COMPRESSION}"
        )
    actual_size = parquet_path.stat().st_size
    if actual_size != manifest["parquet_file_size"]:
        raise PartitionIntegrityError(
            f"Partition {normalized_month} file size does not match the manifest"
        )
    actual_sha = _sha256_file(parquet_path)
    if actual_sha != manifest["parquet_sha256"]:
        raise PartitionIntegrityError(
            f"Partition {normalized_month} SHA-256 does not match the manifest"
        )
    return PartitionVerification(
        month=normalized_month,
        row_count=manifest["row_count"],
        relative_parquet_path=manifest["relative_parquet_path"],
        parquet_sha256=actual_sha,
        parquet_file_size=actual_size,
    )


def write_monthly_fact_partitions(
    fact: pd.DataFrame,
    output_root: Path,
) -> WriteResult:
    """Write deterministic month partitions without overwriting existing data."""
    validated = validate_monthly_fact(fact)
    root = _require_path(output_root)
    _validate_decimal_encoding(validated)
    if validated.empty:
        return WriteResult((), (), 0)

    months = tuple(sorted(validated["month"].unique().tolist()))
    schema_root = _schema_root(root)
    schema_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    unchanged: list[str] = []

    for month in months:
        normalized_month = _validate_month(month)
        final_dir = _partition_dir(root, normalized_month)
        existing_verification: PartitionVerification | None = None
        if final_dir.exists():
            if not final_dir.is_dir():
                raise PartitionIntegrityError(
                    f"Partition path for {normalized_month} is not a directory"
                )
            existing_verification = verify_monthly_fact_partition(root, normalized_month)

        month_fact = (
            validated.loc[validated["month"].eq(normalized_month), MONTHLY_FACT_COLUMNS]
            .sort_values(list(GRAIN_COLUMNS), kind="stable")
            .reset_index(drop=True)
        )
        temp_dir = _create_temp_partition_dir(schema_root, normalized_month)
        try:
            candidate_manifest = _write_candidate(month_fact, normalized_month, temp_dir)
            if existing_verification is not None:
                if (
                    candidate_manifest["parquet_sha256"]
                    == existing_verification.parquet_sha256
                    and candidate_manifest["parquet_file_size"]
                    == existing_verification.parquet_file_size
                    and candidate_manifest["row_count"]
                    == existing_verification.row_count
                ):
                    unchanged.append(normalized_month)
                    continue
                raise PartitionConflictError(
                    f"Partition {normalized_month} already exists with different content"
                )

            if final_dir.exists():
                raced = verify_monthly_fact_partition(root, normalized_month)
                if (
                    candidate_manifest["parquet_sha256"] == raced.parquet_sha256
                    and candidate_manifest["parquet_file_size"] == raced.parquet_file_size
                    and candidate_manifest["row_count"] == raced.row_count
                ):
                    unchanged.append(normalized_month)
                    continue
                raise PartitionConflictError(
                    f"Partition {normalized_month} appeared with different content"
                )
            temp_dir.replace(final_dir)
            written.append(normalized_month)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    return WriteResult(tuple(written), tuple(unchanged), len(validated))


def _normalize_columns(columns: Sequence[str] | None) -> tuple[str, ...]:
    if columns is None:
        return MONTHLY_FACT_COLUMNS
    if isinstance(columns, (str, bytes)):
        raise InvalidPartitionRequestError("columns must be a sequence of column names")
    normalized = tuple(columns)
    if len(set(normalized)) != len(normalized):
        raise InvalidPartitionRequestError("columns must not contain duplicates")
    unknown = [column for column in normalized if column not in MONTHLY_FACT_COLUMNS]
    if unknown:
        raise InvalidPartitionRequestError(f"Unknown monthly fact columns: {unknown}")
    return normalized


def _discover_months(output_root: Path) -> tuple[str, ...]:
    root = _schema_root(output_root)
    if not root.is_dir():
        return ()
    months: list[str] = []
    for child in root.iterdir():
        if not child.is_dir() or not child.name.startswith("month="):
            continue
        month = child.name.removeprefix("month=")
        try:
            months.append(_validate_month(month))
        except InvalidPartitionRequestError as exc:
            raise PartitionIntegrityError(
                f"Unexpected partition directory: {child.name}"
            ) from exc
    return tuple(sorted(months))


def _normalize_months(
    output_root: Path,
    months: Iterable[str] | None,
) -> tuple[str, ...]:
    available = _discover_months(output_root)
    if months is None:
        return available
    if isinstance(months, (str, bytes)):
        raise InvalidPartitionRequestError("months must be a sequence of YYYYMM values")
    requested = tuple(_validate_month(month) for month in months)
    if len(set(requested)) != len(requested):
        raise InvalidPartitionRequestError("months must not contain duplicates")
    unknown = sorted(set(requested) - set(available))
    if unknown:
        raise InvalidPartitionRequestError(f"Unknown month partitions: {unknown}")
    return tuple(sorted(requested))


def _empty_projection(columns: Sequence[str]) -> pd.DataFrame:
    return empty_monthly_fact().loc[:, list(columns)].copy()


def _restore_pandas_contract(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    result = frame.loc[:, list(columns)].copy()
    for column in columns:
        if column in STRING_COLUMNS:
            result[column] = result[column].astype("string")
        elif column in COUNT_COLUMNS:
            result[column] = result[column].astype("Int64")
        elif column in DECIMAL_COLUMNS:
            result[column] = result[column].astype("object")
    return result


def read_monthly_fact_partitions(
    output_root: Path,
    months: Iterable[str] | None = None,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Read selected month partitions with pruning and column projection.

    This normal read path validates manifest metadata, row counts, and requested
    Arrow fields, but intentionally does not hash entire Parquet files. Call
    :func:`verify_monthly_fact_partition` for the explicit integrity check.
    """
    root = _require_path(output_root)
    requested_columns = _normalize_columns(columns)
    requested_months = _normalize_months(root, months)
    if not requested_months:
        return _empty_projection(requested_columns)

    frames: list[pd.DataFrame] = []
    for month in requested_months:
        _, _, parquet_file = _inspect_partition_without_checksum(
            root,
            month,
            columns=requested_columns,
        )
        try:
            table = parquet_file.read(columns=list(requested_columns))
        except (OSError, pa.ArrowException) as exc:
            raise PartitionIntegrityError(
                f"Partition {month} could not be read"
            ) from exc
        frames.append(_restore_pandas_contract(table.to_pandas(), requested_columns))

    result = pd.concat(frames, ignore_index=True)
    result = _restore_pandas_contract(result, requested_columns)
    if requested_columns == MONTHLY_FACT_COLUMNS:
        result = result.sort_values(list(GRAIN_COLUMNS), kind="stable").reset_index(drop=True)
        return validate_monthly_fact(result)
    return result.reset_index(drop=True)
