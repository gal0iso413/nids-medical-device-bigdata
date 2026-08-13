"""Single-writer checkpoint and reducer for classified NIDS supply batches.

The module deliberately starts after the PR-03B1 exact three-key join.  It
does not open Excel workbooks, execute the master join, or publish Parquet.
Every normal PR-03A row is persisted as matched or unmatched, while only new
matched rows affect the incremental PR-01 monthly accumulator.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import secrets
import sqlite3
from typing import Any, Final, Iterable, Sequence

import pandas as pd
import numpy as np

from data_pipeline.aggregates.company_counterparty_product_month import (
    validate_forward_supply_rows,
)
from data_pipeline.contracts.supply_monthly import (
    FACT_SCHEMA_NAME,
    FACT_SCHEMA_VERSION,
    MONTHLY_FACT_COLUMNS,
    MONTHLY_FACT_SCHEMA,
    SOURCE_REQUIRED_COLUMNS,
    assign_product_ids,
    empty_monthly_fact,
    normalize_source_rows,
    validate_monthly_fact,
)
from data_pipeline.ingest.nids_supply_excel import (
    ADAPTER_CONTRACT_VERSION,
    SourceLineage,
    SupplyIngestionReport,
)
from data_pipeline.storage.master_product_lookup import (
    LOGICAL_SCHEMA_VERSION as MASTER_SCHEMA_VERSION,
    STORAGE_CONTRACT_VERSION as MASTER_STORAGE_VERSION,
    MasterLookupVerification,
)


DATASET_NAME: Final = "supply_monthly_orchestration"
CHECKPOINT_CONTRACT_VERSION: Final = "1.0.0"
REDUCER_CONTRACT_VERSION: Final = "1.0.0"
DATABASE_FILENAME: Final = "checkpoint.sqlite"
RUN_MANIFEST_FILENAME: Final = "_run_manifest.json"
SEALED_MANIFEST_FILENAME: Final = "_sealed_manifest.json"
DIAGNOSTIC_LIMIT: Final = 20
ESTIMATED_FACT_BYTES_PER_GRAIN: Final = 4096
_HEX_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_ROW_PATTERN: Final = re.compile(r"^nids-row-v1:([0-9a-f]{64})$")
_MONTH_PATTERN: Final = re.compile(r"^\d{6}$")
_OPTIONAL_DIMENSIONS: Final[tuple[str, ...]] = (
    "item_group_id",
    "item_name_id",
    "supplier_type",
    "receiver_type",
    "supplier_region",
    "receiver_region",
)
_DECIMAL_FIELDS: Final[tuple[str, ...]] = (
    "amount_clean",
    "raw_supply_qty",
    "piece_qty",
)
_BUSINESS_FIELDS: Final[tuple[str, ...]] = tuple(
    column
    for column in SOURCE_REQUIRED_COLUMNS
    if column not in {"source_version", "source_row_id"}
) + ("row_quality_flags",)
_GRAIN: Final[tuple[str, ...]] = (
    "month",
    "src_company_id",
    "dst_company_id",
    "product_id",
)


class SupplyMonthlyCheckpointError(RuntimeError):
    """Base error for the PR-03B2A checkpoint contract."""


class CheckpointLineageError(SupplyMonthlyCheckpointError):
    """Raised when an existing run does not match immutable lineage."""


class CheckpointIntegrityError(SupplyMonthlyCheckpointError):
    """Raised when an active or sealed checkpoint is incomplete or damaged."""


class SourceRowConflictError(SupplyMonthlyCheckpointError):
    """Raised when one logical source row has different content/classification."""


class CheckpointSealedError(SupplyMonthlyCheckpointError):
    """Raised when a caller attempts to mutate a sealed checkpoint."""


class EmptySupplyInputError(SupplyMonthlyCheckpointError):
    """Raised when EOF accounting proves that no eligible input was emitted."""


class AllRowsUnmatchedError(SupplyMonthlyCheckpointError):
    """Raised when no emitted source row has an exact master match."""


class CheckpointMemoryLimitError(SupplyMonthlyCheckpointError):
    """Raised before loading a month whose conservative estimate is unsafe."""


@dataclass(frozen=True)
class BatchApplyResult:
    rows_input: int
    rows_new: int
    rows_replayed: int
    matched_new: int
    unmatched_new: int


@dataclass(frozen=True)
class SealedCheckpointResult:
    run_id: str
    months: tuple[str, ...]
    ledger_rows: int
    matched_rows: int
    unmatched_rows: int
    relative_database_path: str
    database_sha256: str
    database_file_size: int
    fact_fingerprints: tuple[tuple[str, str], ...]


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, Counter):
        return {str(key): value[key] for key in sorted(value)}
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _json_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (str, int, bool)):
        return value
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise CheckpointIntegrityError("Could not checksum checkpoint SQLite") from exc
    return digest.hexdigest()


def _fact_schema_fingerprint() -> str:
    return _sha256_bytes(
        _canonical_json_bytes(
            {
                "name": FACT_SCHEMA_NAME,
                "version": FACT_SCHEMA_VERSION,
                "schema": MONTHLY_FACT_SCHEMA,
            }
        )
    )


FACT_SCHEMA_FINGERPRINT: Final = _fact_schema_fingerprint()


def _run_payload(
    supply_lineage: SourceLineage,
    master: MasterLookupVerification,
) -> dict[str, Any]:
    return {
        "checkpoint_contract_version": CHECKPOINT_CONTRACT_VERSION,
        "dataset_name": DATASET_NAME,
        "fact_schema_fingerprint": FACT_SCHEMA_FINGERPRINT,
        "fact_schema_name": FACT_SCHEMA_NAME,
        "fact_schema_version": FACT_SCHEMA_VERSION,
        "master": {
            "database_file_size": master.database_file_size,
            "database_sha256": master.database_sha256,
            "logical_schema_version": MASTER_SCHEMA_VERSION,
            "source_hash": master.source_hash,
            "source_version": master.source_version,
            "storage_contract_version": MASTER_STORAGE_VERSION,
            "unique_key_count": master.unique_key_count,
        },
        "reducer_contract_version": REDUCER_CONTRACT_VERSION,
        "supply": {
            "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
            "source_version": supply_lineage.source_version,
            "workbooks": [
                {
                    "byte_size": item.byte_size,
                    "logical_name": item.logical_name,
                    "sha256": item.sha256,
                }
                for item in supply_lineage.workbooks
            ],
        },
    }


def _manifest_with_run_id(payload: dict[str, Any]) -> dict[str, Any]:
    run_id = _sha256_bytes(_canonical_json_bytes(payload))
    return {**payload, "run_id": run_id}


def _run_dir(checkpoint_root: Path, run_id: str) -> Path:
    if not isinstance(checkpoint_root, Path):
        raise TypeError("checkpoint_root must be pathlib.Path")
    if not _HEX_PATTERN.fullmatch(run_id):
        raise ValueError("run_id must be 64 lowercase hexadecimal characters")
    return (
        checkpoint_root
        / DATASET_NAME
        / f"checkpoint_version={CHECKPOINT_CONTRACT_VERSION}"
        / f"run_id={run_id}"
    )


def _relative_database_path(run_id: str) -> str:
    return PurePosixPath(
        DATASET_NAME,
        f"checkpoint_version={CHECKPOINT_CONTRACT_VERSION}",
        f"run_id={run_id}",
        DATABASE_FILENAME,
    ).as_posix()


def _write_canonical(path: Path, value: dict[str, Any]) -> None:
    candidate = path.with_name(f".{path.name}.tmp-{secrets.token_hex(6)}")
    try:
        candidate.write_bytes(_canonical_json_bytes(value))
        candidate.replace(path)
    except OSError as exc:
        raise CheckpointIntegrityError(f"Could not write {path.name}") from exc
    finally:
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass


def _read_canonical(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckpointIntegrityError(f"Checkpoint {path.name} is unreadable") from exc
    if not isinstance(value, dict) or raw != _canonical_json_bytes(value):
        raise CheckpointIntegrityError(f"Checkpoint {path.name} is not canonical JSON")
    return value


def _decimal_add(left: str | None, right: str | None) -> str | None:
    if left is None:
        return right
    if right is None:
        return left
    return format(Decimal(left) + Decimal(right), "f")


def _schema_sql() -> str:
    dimension_columns = ",\n".join(
        f"{name}_valid_count INTEGER NOT NULL, {name}_candidate TEXT, {name}_conflict INTEGER NOT NULL CHECK({name}_conflict IN (0,1))"
        for name in _OPTIONAL_DIMENSIONS
    )
    return f"""
CREATE TABLE run_metadata(
  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
  run_id TEXT NOT NULL,
  supply_source_version TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('active','sealed'))
);
CREATE TABLE source_row_ledger(
  source_row_digest BLOB PRIMARY KEY CHECK(length(source_row_digest)=32),
  content_digest BLOB NOT NULL CHECK(length(content_digest)=32),
  month TEXT NOT NULL CHECK(length(month)=6),
  classification INTEGER NOT NULL CHECK(classification IN (0,1))
) WITHOUT ROWID;
CREATE TABLE grain_accumulator(
  month TEXT NOT NULL,
  src_company_id TEXT NOT NULL,
  dst_company_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  tx_count INTEGER NOT NULL,
  amount_sum TEXT,
  amount_valid_count INTEGER NOT NULL,
  raw_supply_qty_sum TEXT,
  raw_supply_qty_valid_count INTEGER NOT NULL,
  piece_qty_sum TEXT,
  piece_qty_valid_count INTEGER NOT NULL,
  udi_valid_count INTEGER NOT NULL,
  {dimension_columns},
  PRIMARY KEY(month,src_company_id,dst_company_id,product_id)
) WITHOUT ROWID;
CREATE TABLE grain_distinct_udi(
  month TEXT NOT NULL, src_company_id TEXT NOT NULL, dst_company_id TEXT NOT NULL,
  product_id TEXT NOT NULL, udi TEXT NOT NULL,
  PRIMARY KEY(month,src_company_id,dst_company_id,product_id,udi)
) WITHOUT ROWID;
CREATE TABLE grain_distinct_day(
  month TEXT NOT NULL, src_company_id TEXT NOT NULL, dst_company_id TEXT NOT NULL,
  product_id TEXT NOT NULL, active_day TEXT NOT NULL,
  PRIMARY KEY(month,src_company_id,dst_company_id,product_id,active_day)
) WITHOUT ROWID;
CREATE TABLE grain_quality_flag(
  month TEXT NOT NULL, src_company_id TEXT NOT NULL, dst_company_id TEXT NOT NULL,
  product_id TEXT NOT NULL, quality_flag TEXT NOT NULL,
  PRIMARY KEY(month,src_company_id,dst_company_id,product_id,quality_flag)
) WITHOUT ROWID;
CREATE TABLE adapter_final_report(
  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
  report_json TEXT NOT NULL,
  report_sha256 TEXT NOT NULL
);
"""


def _open_active_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.create_function("decimal_add", 2, _decimal_add, deterministic=True)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA synchronous=NORMAL")
    mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if str(mode).lower() != "wal":
        connection.close()
        raise CheckpointIntegrityError("Checkpoint SQLite could not enable WAL mode")
    return connection


def _create_database(path: Path, run_manifest: dict[str, Any]) -> sqlite3.Connection:
    connection = _open_active_database(path)
    try:
        connection.executescript(_schema_sql())
        connection.execute("PRAGMA user_version=1")
        connection.execute(
            "INSERT INTO run_metadata VALUES (1,?,?, 'active')",
            (run_manifest["run_id"], run_manifest["supply"]["source_version"]),
        )
        connection.commit()
        return connection
    except Exception:
        connection.close()
        raise


def _quick_check(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        raise CheckpointIntegrityError("Checkpoint has an unexpected open transaction")
    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise CheckpointIntegrityError("Checkpoint SQLite quick_check failed")
    if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
        raise CheckpointIntegrityError("Checkpoint SQLite schema version is invalid")
    expected = {
        "run_metadata",
        "source_row_ledger",
        "grain_accumulator",
        "grain_distinct_udi",
        "grain_distinct_day",
        "grain_quality_flag",
        "adapter_final_report",
    }
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if tables != expected:
        raise CheckpointIntegrityError("Checkpoint SQLite table set is invalid")


def _verify_reducer_invariants(connection: sqlite3.Connection) -> None:
    ledger = connection.execute(
        "SELECT COUNT(*),COALESCE(SUM(classification),0) FROM source_row_ledger"
    ).fetchone()
    accumulated = int(
        connection.execute(
            "SELECT COALESCE(SUM(tx_count),0) FROM grain_accumulator"
        ).fetchone()[0]
    )
    if int(ledger[1]) != accumulated:
        raise CheckpointIntegrityError("Matched ledger and accumulator counts differ")
    invalid_accumulator = connection.execute(
        "SELECT COUNT(*) FROM grain_accumulator WHERE tx_count<1 "
        "OR amount_valid_count<0 OR amount_valid_count>tx_count "
        "OR raw_supply_qty_valid_count<0 OR raw_supply_qty_valid_count>tx_count "
        "OR piece_qty_valid_count<0 OR piece_qty_valid_count>tx_count "
        "OR udi_valid_count<0 OR udi_valid_count>tx_count"
    ).fetchone()[0]
    if invalid_accumulator:
        raise CheckpointIntegrityError("Checkpoint accumulator counts are invalid")
    for table in ("grain_distinct_udi", "grain_distinct_day", "grain_quality_flag"):
        orphan = connection.execute(
            f"SELECT COUNT(*) FROM {table} d LEFT JOIN grain_accumulator g "
            "USING(month,src_company_id,dst_company_id,product_id) "
            "WHERE g.product_id IS NULL"
        ).fetchone()[0]
        if orphan:
            raise CheckpointIntegrityError(f"Checkpoint {table} contains orphan state")


def _canonical_flags(value: Any) -> str:
    flags = {
        flag.strip()
        for flag in str(value or "").replace("|", ";").split(";")
        if flag.strip()
    }
    return ";".join(sorted(flags))


def _content_digest(row: pd.Series) -> bytes:
    payload = {
        column: _json_value(
            _canonical_flags(row[column]) if column == "row_quality_flags" else row[column]
        )
        for column in _BUSINESS_FIELDS
    }
    return sha256(_canonical_json_bytes(payload)).digest()


def _source_digest(source_row_id: str) -> bytes:
    match = _SOURCE_ROW_PATTERN.fullmatch(source_row_id)
    if match is None:
        raise SourceRowConflictError(
            "source_row_id must match nids-row-v1:<64 lowercase hex>"
        )
    return bytes.fromhex(match.group(1))


def _source_row_id(digest: bytes) -> str:
    if len(digest) != 32:
        raise CheckpointIntegrityError("Ledger source-row digest length is invalid")
    return f"nids-row-v1:{digest.hex()}"


def _classification_by_id(batch: pd.DataFrame, matched_mask: Sequence[bool]) -> dict[str, int]:
    if len(matched_mask) != len(batch):
        raise ValueError("matched_mask length must equal batch length")
    result: dict[str, int] = {}
    for raw_id, matched in zip(batch["source_row_id"], matched_mask):
        if not isinstance(matched, (bool, np.bool_)):
            raise TypeError("matched_mask must contain bool values")
        source_id = str(raw_id).strip()
        _source_digest(source_id)
        classification = int(matched)
        previous = result.get(source_id)
        if previous is not None and previous != classification:
            raise SourceRowConflictError(
                f"One source_row_id has conflicting classifications: {source_id}"
            )
        result[source_id] = classification
    return result


def _upsert_sql() -> str:
    columns = [
        "month", "src_company_id", "dst_company_id", "product_id", "tx_count",
        "amount_sum", "amount_valid_count", "raw_supply_qty_sum",
        "raw_supply_qty_valid_count", "piece_qty_sum", "piece_qty_valid_count",
        "udi_valid_count",
    ]
    for name in _OPTIONAL_DIMENSIONS:
        columns.extend((f"{name}_valid_count", f"{name}_candidate", f"{name}_conflict"))
    updates = [
        "tx_count=tx_count+excluded.tx_count",
        "amount_sum=decimal_add(amount_sum,excluded.amount_sum)",
        "amount_valid_count=amount_valid_count+excluded.amount_valid_count",
        "raw_supply_qty_sum=decimal_add(raw_supply_qty_sum,excluded.raw_supply_qty_sum)",
        "raw_supply_qty_valid_count=raw_supply_qty_valid_count+excluded.raw_supply_qty_valid_count",
        "piece_qty_sum=decimal_add(piece_qty_sum,excluded.piece_qty_sum)",
        "piece_qty_valid_count=piece_qty_valid_count+excluded.piece_qty_valid_count",
        "udi_valid_count=udi_valid_count+excluded.udi_valid_count",
    ]
    for name in _OPTIONAL_DIMENSIONS:
        candidate = f"{name}_candidate"
        conflict = f"{name}_conflict"
        valid = f"{name}_valid_count"
        mismatch = (
            f"({candidate} IS NOT NULL AND excluded.{candidate} IS NOT NULL "
            f"AND {candidate}<>excluded.{candidate})"
        )
        updates.extend(
            (
                f"{valid}={valid}+excluded.{valid}",
                f"{conflict}=CASE WHEN {conflict}=1 OR excluded.{conflict}=1 OR {mismatch} THEN 1 ELSE 0 END",
                f"{candidate}=CASE WHEN {conflict}=1 OR excluded.{conflict}=1 OR {mismatch} THEN NULL WHEN {candidate} IS NULL THEN excluded.{candidate} ELSE {candidate} END",
            )
        )
    placeholders = ",".join("?" for _ in columns)
    return (
        f"INSERT INTO grain_accumulator({','.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(month,src_company_id,dst_company_id,product_id) DO UPDATE SET {','.join(updates)}"
    )


_UPSERT_SQL: Final = _upsert_sql()


def _accumulator_record(row: pd.Series) -> tuple[Any, ...]:
    values: list[Any] = [
        row["month"], row["src_company_id"], row["dst_company_id"], row["product_id"], 1,
    ]
    for column in _DECIMAL_FIELDS:
        value = row[column]
        valid = value is not None and value is not pd.NA and not pd.isna(value)
        values.extend((format(value, "f") if valid else None, int(valid)))
    udi = row["udi"]
    udi_valid = udi is not None and udi is not pd.NA and not pd.isna(udi)
    values.append(int(udi_valid))
    for name in _OPTIONAL_DIMENSIONS:
        value = row[name]
        valid = value is not None and value is not pd.NA and not pd.isna(value)
        values.extend((int(valid), str(value) if valid else None, 0))
    return tuple(values)


def _normalized_batch(
    batch: pd.DataFrame,
    matched_mask: Sequence[bool],
    supply_source_version: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    if not isinstance(batch, pd.DataFrame):
        raise TypeError("batch must be a pandas DataFrame")
    if "source_row_id" not in batch.columns:
        raise SourceRowConflictError("batch is missing source_row_id")
    classifications = _classification_by_id(batch, matched_mask)
    normalized = normalize_source_rows(batch)
    versions = normalized["source_version"].dropna().unique().tolist()
    if versions != [supply_source_version]:
        raise CheckpointLineageError("Classified batch supply lineage does not match run")
    validate_forward_supply_rows(normalized)
    normalized["month"] = normalized["supply_date"].dt.strftime("%Y%m")
    return normalized, classifications


class SupplyMonthlyCheckpoint:
    """One active or sealed run-scoped single-writer checkpoint."""

    def __init__(self, run_dir: Path, run_manifest: dict[str, Any], connection: sqlite3.Connection):
        self.run_dir = run_dir
        self.run_manifest = run_manifest
        self.run_id = str(run_manifest["run_id"])
        self._connection = connection
        self._closed = False
        self.verify_active()

    def __enter__(self) -> "SupplyMonthlyCheckpoint":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()

    @property
    def state(self) -> str:
        if self._closed:
            sealed = self.run_dir / SEALED_MANIFEST_FILENAME
            return "sealed" if sealed.is_file() else "closed"
        row = self._connection.execute(
            "SELECT state FROM run_metadata WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise CheckpointIntegrityError("Checkpoint run metadata is missing")
        return str(row[0])

    def close(self) -> None:
        if self._closed:
            return
        self._connection.close()
        self._closed = True

    def verify_active(self) -> None:
        if self._closed:
            raise CheckpointIntegrityError("Checkpoint is closed")
        _quick_check(self._connection)
        row = self._connection.execute(
            "SELECT run_id,supply_source_version,state FROM run_metadata WHERE singleton=1"
        ).fetchone()
        if row is None or row["run_id"] != self.run_id:
            raise CheckpointLineageError("Checkpoint run metadata does not match manifest")
        if row["supply_source_version"] != self.run_manifest["supply"]["source_version"]:
            raise CheckpointLineageError("Checkpoint supply lineage does not match manifest")
        if row["state"] not in {"active", "sealed"}:
            raise CheckpointIntegrityError("Checkpoint state is invalid")
        _verify_reducer_invariants(self._connection)

    def apply_classified_batch(
        self,
        batch: pd.DataFrame,
        *,
        matched_mask: Sequence[bool],
    ) -> BatchApplyResult:
        if self.state != "active":
            raise CheckpointSealedError("A sealed checkpoint cannot accept batches")
        normalized, classifications = _normalized_batch(
            batch, matched_mask, self.run_manifest["supply"]["source_version"]
        )
        records: list[tuple[bytes, bytes, str, int, int]] = []
        for position, row in normalized.iterrows():
            source_id = str(row["source_row_id"])
            records.append(
                (
                    _source_digest(source_id),
                    _content_digest(row),
                    str(row["month"]),
                    classifications[source_id],
                    position,
                )
            )
        connection = self._connection
        new_positions: list[int] = []
        matched_new = 0
        unmatched_new = 0
        try:
            connection.execute("BEGIN IMMEDIATE")
            for digest, content, month, classification, position in records:
                existing = connection.execute(
                    "SELECT content_digest,classification FROM source_row_ledger WHERE source_row_digest=?",
                    (digest,),
                ).fetchone()
                if existing is not None:
                    if bytes(existing[0]) != content or int(existing[1]) != classification:
                        raise SourceRowConflictError(
                            "Source row content/classification conflict: " + _source_row_id(digest)
                        )
                    continue
                connection.execute(
                    "INSERT INTO source_row_ledger VALUES (?,?,?,?)",
                    (digest, content, month, classification),
                )
                new_positions.append(position)
                if classification:
                    matched_new += 1
                else:
                    unmatched_new += 1

            if new_positions:
                new_rows = normalized.loc[new_positions].copy()
                matched_rows = new_rows.loc[
                    new_rows["source_row_id"].map(classifications).astype(bool)
                ].copy()
                if not matched_rows.empty:
                    matched_rows = assign_product_ids(matched_rows)
                    connection.executemany(
                        _UPSERT_SQL,
                        (_accumulator_record(row) for _, row in matched_rows.iterrows()),
                    )
                    udi_rows: list[tuple[str, str, str, str, str]] = []
                    day_rows: list[tuple[str, str, str, str, str]] = []
                    flag_rows: list[tuple[str, str, str, str, str]] = []
                    for _, row in matched_rows.iterrows():
                        grain = tuple(str(row[column]) for column in _GRAIN)
                        udi = row["udi"]
                        if udi is not None and udi is not pd.NA and not pd.isna(udi):
                            udi_rows.append((*grain, str(udi)))
                        day_rows.append((*grain, row["supply_date"].strftime("%Y%m%d")))
                        for flag in _canonical_flags(row["row_quality_flags"]).split(";"):
                            if flag:
                                flag_rows.append((*grain, flag))
                    connection.executemany(
                        "INSERT OR IGNORE INTO grain_distinct_udi VALUES (?,?,?,?,?)", udi_rows
                    )
                    connection.executemany(
                        "INSERT OR IGNORE INTO grain_distinct_day VALUES (?,?,?,?,?)", day_rows
                    )
                    connection.executemany(
                        "INSERT OR IGNORE INTO grain_quality_flag VALUES (?,?,?,?,?)", flag_rows
                    )
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        return BatchApplyResult(
            rows_input=len(batch),
            rows_new=len(new_positions),
            rows_replayed=len(batch) - len(new_positions),
            matched_new=matched_new,
            unmatched_new=unmatched_new,
        )

    def _fact_for_month(self, month: str) -> pd.DataFrame:
        return _fact_for_month(self._connection, month, self.run_manifest["supply"]["source_version"])

    def seal(self, *, adapter_report: SupplyIngestionReport) -> SealedCheckpointResult:
        if self.state == "sealed":
            raise CheckpointSealedError("Checkpoint is already sealed")
        adapter_report.validate_accounting()
        if adapter_report.rows_read == 0 or adapter_report.rows_emitted == 0:
            raise EmptySupplyInputError("Supply stream emitted no eligible rows")
        counts = self._connection.execute(
            "SELECT COUNT(*),COALESCE(SUM(classification),0) FROM source_row_ledger"
        ).fetchone()
        ledger_rows, matched_rows = int(counts[0]), int(counts[1])
        unmatched_rows = ledger_rows - matched_rows
        if ledger_rows == 0:
            raise EmptySupplyInputError("Checkpoint ledger is empty")
        if matched_rows == 0:
            raise AllRowsUnmatchedError("All emitted source rows were unmatched")
        if adapter_report.rows_emitted < ledger_rows:
            raise CheckpointIntegrityError("Adapter report emitted rows are below ledger rows")

        months = tuple(
            row[0]
            for row in self._connection.execute(
                "SELECT DISTINCT month FROM source_row_ledger ORDER BY month"
            )
        )
        fact_fingerprints: list[tuple[str, str]] = []
        month_entries: list[dict[str, Any]] = []
        accumulator_tx = int(
            self._connection.execute(
                "SELECT COALESCE(SUM(tx_count),0) FROM grain_accumulator"
            ).fetchone()[0]
        )
        if accumulator_tx != matched_rows:
            raise CheckpointIntegrityError("Matched ledger and accumulator counts differ")
        for month in months:
            fact = self._fact_for_month(month)
            fingerprint = _fact_fingerprint(fact)
            fact_fingerprints.append((month, fingerprint))
            month_counts = self._connection.execute(
                "SELECT COUNT(*),COALESCE(SUM(classification),0) FROM source_row_ledger WHERE month=?",
                (month,),
            ).fetchone()
            grain_count = len(fact)
            month_entries.append(
                {
                    "fact_fingerprint": fingerprint,
                    "grain_count": grain_count,
                    "matched_rows": int(month_counts[1]),
                    "month": month,
                    "unmatched_rows": int(month_counts[0]) - int(month_counts[1]),
                }
            )

        report_payload = _json_value(adapter_report)
        report_json = _canonical_json_bytes(report_payload).decode("utf-8")
        report_sha = _sha256_bytes(report_json.encode("utf-8"))
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._connection.execute(
                "INSERT INTO adapter_final_report VALUES (1,?,?)",
                (report_json, report_sha),
            )
            self._connection.execute(
                "UPDATE run_metadata SET state='sealed' WHERE singleton=1"
            )
            self._connection.commit()
            self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        except Exception:
            if self._connection.in_transaction:
                self._connection.rollback()
            raise
        self.close()

        database_path = self.run_dir / DATABASE_FILENAME
        for suffix in ("-wal", "-shm", "-journal"):
            if Path(str(database_path) + suffix).exists():
                raise CheckpointIntegrityError("SQLite sidecar remains after seal")
        try:
            database_size = database_path.stat().st_size
        except OSError as exc:
            raise CheckpointIntegrityError("Could not stat sealed checkpoint SQLite") from exc
        database_sha = _sha256_file(database_path)
        sample_connection = sqlite3.connect(database_path)
        try:
            unmatched_sample = [
                _source_row_id(bytes(row[0]))
                for row in sample_connection.execute(
                    "SELECT source_row_digest FROM source_row_ledger "
                    "WHERE classification=0 ORDER BY source_row_digest LIMIT ?",
                    (DIAGNOSTIC_LIMIT,),
                ).fetchall()
            ]
        finally:
            sample_connection.close()
        sealed_manifest = {
            "adapter_report": report_payload,
            "adapter_report_sha256": report_sha,
            "checkpoint_contract_version": CHECKPOINT_CONTRACT_VERSION,
            "database_file_size": database_size,
            "database_sha256": database_sha,
            "dataset_name": DATASET_NAME,
            "fact_schema_fingerprint": FACT_SCHEMA_FINGERPRINT,
            "ledger_rows": ledger_rows,
            "matched_rows": matched_rows,
            "months": month_entries,
            "quality_report": {
                "adapter_rows_emitted": adapter_report.rows_emitted,
                "adapter_rows_read": adapter_report.rows_read,
                "adapter_rows_rejected": adapter_report.rows_rejected,
                "exact_duplicate_rows": max(adapter_report.rows_emitted - ledger_rows, 0),
                "unmatched_omitted": max(unmatched_rows - len(unmatched_sample), 0),
                "unmatched_source_row_ids": unmatched_sample,
            },
            "relative_database_path": _relative_database_path(self.run_id),
            "run_id": self.run_id,
            "run_manifest_sha256": _sha256_file(self.run_dir / RUN_MANIFEST_FILENAME),
            "unmatched_rows": unmatched_rows,
        }
        _write_canonical(self.run_dir / SEALED_MANIFEST_FILENAME, sealed_manifest)
        return SealedCheckpointResult(
            self.run_id,
            months,
            ledger_rows,
            matched_rows,
            unmatched_rows,
            sealed_manifest["relative_database_path"],
            database_sha,
            database_size,
            tuple(fact_fingerprints),
        )


def _fact_for_month(
    connection: sqlite3.Connection,
    month: str,
    source_version: str,
) -> pd.DataFrame:
    if not _MONTH_PATTERN.fullmatch(month):
        raise ValueError("month must be YYYYMM")
    rows = connection.execute(
        "SELECT * FROM grain_accumulator WHERE month=? ORDER BY src_company_id,dst_company_id,product_id",
        (month,),
    ).fetchall()
    if not rows:
        return empty_monthly_fact()
    udi_counts = {
        tuple(row[:4]): int(row[4])
        for row in connection.execute(
            "SELECT month,src_company_id,dst_company_id,product_id,COUNT(*) FROM grain_distinct_udi WHERE month=? GROUP BY month,src_company_id,dst_company_id,product_id",
            (month,),
        )
    }
    day_counts = {
        tuple(row[:4]): int(row[4])
        for row in connection.execute(
            "SELECT month,src_company_id,dst_company_id,product_id,COUNT(*) FROM grain_distinct_day WHERE month=? GROUP BY month,src_company_id,dst_company_id,product_id",
            (month,),
        )
    }
    flags: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    for flag_row in connection.execute(
        "SELECT month,src_company_id,dst_company_id,product_id,quality_flag FROM grain_quality_flag WHERE month=? ORDER BY month,src_company_id,dst_company_id,product_id,quality_flag",
        (month,),
    ):
        flags[tuple(flag_row[:4])].add(str(flag_row[4]))

    result: list[dict[str, Any]] = []
    decimal_map = (
        ("amount_sum", "amount_sum_clean", "amount_valid_count", "amount_valid_row_count", "amount_clean"),
        ("raw_supply_qty_sum", "raw_supply_qty_sum", "raw_supply_qty_valid_count", "raw_supply_qty_valid_row_count", "raw_supply_qty"),
        ("piece_qty_sum", "piece_qty_sum", "piece_qty_valid_count", "piece_qty_valid_row_count", "piece_qty"),
    )
    for row in rows:
        key = tuple(row[column] for column in _GRAIN)
        tx_count = int(row["tx_count"])
        fact_row: dict[str, Any] = {
            "month": row["month"],
            "src_company_id": row["src_company_id"],
            "dst_company_id": row["dst_company_id"],
            "product_id": row["product_id"],
            "tx_count": tx_count,
            "unique_udi_count": udi_counts.get(key, 0),
            "active_day_count": day_counts.get(key, 0),
            "source_version": source_version,
        }
        grain_flags = set(flags.get(key, set()))
        for stored_sum, fact_sum, stored_count, fact_count, source_name in decimal_map:
            count = int(row[stored_count])
            fact_row[fact_sum] = Decimal(row[stored_sum]) if row[stored_sum] is not None else None
            fact_row[fact_count] = count
            if count == 0:
                grain_flags.add(f"{source_name}_unavailable")
            elif count < tx_count:
                grain_flags.add(f"{source_name}_partial")
        for name in _OPTIONAL_DIMENSIONS:
            valid_count = int(row[f"{name}_valid_count"])
            conflict = bool(row[f"{name}_conflict"])
            fact_row[name] = None if conflict else row[f"{name}_candidate"]
            if valid_count < tx_count:
                grain_flags.add(f"{name}_missing")
            if conflict:
                grain_flags.add(f"{name}_conflict")
        udi_valid = int(row["udi_valid_count"])
        if udi_valid == 0:
            grain_flags.add("udi_unavailable")
        elif udi_valid < tx_count:
            grain_flags.add("udi_partial")
        fact_row["quality_flags"] = ";".join(sorted(grain_flags))
        result.append(fact_row)

    fact = pd.DataFrame(result, columns=MONTHLY_FACT_COLUMNS)
    string_columns = (
        "month", "src_company_id", "dst_company_id", "product_id",
        *_OPTIONAL_DIMENSIONS, "source_version", "quality_flags",
    )
    count_columns = (
        "tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count",
        "piece_qty_valid_row_count", "unique_udi_count", "active_day_count",
    )
    for column in string_columns:
        fact[column] = fact[column].astype("string")
    for column in count_columns:
        fact[column] = fact[column].astype("Int64")
    for column in ("amount_sum_clean", "raw_supply_qty_sum", "piece_qty_sum"):
        fact[column] = fact[column].astype("object")
    return validate_monthly_fact(fact)


def _fact_fingerprint(fact: pd.DataFrame) -> str:
    rows = [
        {column: _json_value(row[column]) for column in MONTHLY_FACT_COLUMNS}
        for _, row in fact.iterrows()
    ]
    return _sha256_bytes(_canonical_json_bytes(rows))


def create_or_open_supply_monthly_checkpoint(
    checkpoint_root: Path,
    *,
    supply_lineage: SourceLineage,
    master_verification: MasterLookupVerification,
) -> SupplyMonthlyCheckpoint:
    payload = _run_payload(supply_lineage, master_verification)
    manifest = _manifest_with_run_id(payload)
    run_dir = _run_dir(checkpoint_root, manifest["run_id"])
    run_manifest_path = run_dir / RUN_MANIFEST_FILENAME
    database_path = run_dir / DATABASE_FILENAME
    if run_dir.exists():
        existing = _read_canonical(run_manifest_path)
        if existing != manifest:
            raise CheckpointLineageError("Existing checkpoint run manifest differs")
        if not database_path.is_file():
            raise CheckpointIntegrityError("Checkpoint SQLite is missing")
        if (run_dir / SEALED_MANIFEST_FILENAME).is_file():
            verify_sealed_supply_checkpoint(checkpoint_root, manifest["run_id"])
            raise CheckpointSealedError("Checkpoint is sealed and immutable")
        connection = _open_active_database(database_path)
        checkpoint = SupplyMonthlyCheckpoint(run_dir, manifest, connection)
        if checkpoint.state != "active":
            checkpoint.close()
            raise CheckpointIntegrityError("Sealed SQLite is missing its sealed manifest")
        return checkpoint
    try:
        run_dir.mkdir(parents=True)
        _write_canonical(run_manifest_path, manifest)
        connection = _create_database(database_path, manifest)
        return SupplyMonthlyCheckpoint(run_dir, manifest, connection)
    except Exception:
        if run_dir.exists() and not database_path.exists():
            for child in run_dir.iterdir():
                child.unlink(missing_ok=True)
            run_dir.rmdir()
        raise


def _sealed_paths(checkpoint_root: Path, run_id: str) -> tuple[Path, Path, Path]:
    run_dir = _run_dir(checkpoint_root, run_id)
    return (
        run_dir / RUN_MANIFEST_FILENAME,
        run_dir / DATABASE_FILENAME,
        run_dir / SEALED_MANIFEST_FILENAME,
    )


def verify_sealed_supply_checkpoint(
    checkpoint_root: Path,
    run_id: str,
) -> SealedCheckpointResult:
    run_manifest_path, database_path, sealed_path = _sealed_paths(checkpoint_root, run_id)
    run_manifest = _read_canonical(run_manifest_path)
    sealed = _read_canonical(sealed_path)
    required_sealed = {
        "adapter_report", "adapter_report_sha256", "checkpoint_contract_version",
        "database_file_size", "database_sha256", "dataset_name",
        "fact_schema_fingerprint", "ledger_rows", "matched_rows", "months",
        "quality_report", "relative_database_path", "run_id",
        "run_manifest_sha256", "unmatched_rows",
    }
    if set(sealed) != required_sealed:
        raise CheckpointIntegrityError("Sealed manifest field set is invalid")
    if run_manifest.get("run_id") != run_id or sealed.get("run_id") != run_id:
        raise CheckpointLineageError("Sealed checkpoint run ID differs")
    if sealed.get("run_manifest_sha256") != _sha256_file(run_manifest_path):
        raise CheckpointIntegrityError("Sealed run manifest checksum differs")
    try:
        size = database_path.stat().st_size
    except OSError as exc:
        raise CheckpointIntegrityError("Sealed checkpoint SQLite is missing") from exc
    checksum = _sha256_file(database_path)
    if sealed.get("database_file_size") != size or sealed.get("database_sha256") != checksum:
        raise CheckpointIntegrityError("Sealed checkpoint SQLite checksum differs")
    uri = database_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        _quick_check(connection)
        _verify_reducer_invariants(connection)
        state = connection.execute("SELECT state FROM run_metadata WHERE singleton=1").fetchone()
        if state is None or state[0] != "sealed":
            raise CheckpointIntegrityError("Checkpoint SQLite is not sealed")
    finally:
        connection.close()
    months = tuple(entry["month"] for entry in sealed["months"])
    fingerprints = tuple(
        (entry["month"], entry["fact_fingerprint"]) for entry in sealed["months"]
    )
    return SealedCheckpointResult(
        run_id,
        months,
        int(sealed["ledger_rows"]),
        int(sealed["matched_rows"]),
        int(sealed["unmatched_rows"]),
        str(sealed["relative_database_path"]),
        checksum,
        size,
        fingerprints,
    )


def read_sealed_month_fact(
    checkpoint_root: Path,
    run_id: str,
    month: str,
    *,
    max_fact_bytes: int,
) -> pd.DataFrame:
    if not isinstance(max_fact_bytes, int) or max_fact_bytes < 1:
        raise ValueError("max_fact_bytes must be a positive integer")
    verification = verify_sealed_supply_checkpoint(checkpoint_root, run_id)
    if month not in verification.months:
        raise ValueError("Unknown sealed month")
    _, database_path, sealed_path = _sealed_paths(checkpoint_root, run_id)
    sealed = _read_canonical(sealed_path)
    entry = next(item for item in sealed["months"] if item["month"] == month)
    estimated = int(entry["grain_count"]) * ESTIMATED_FACT_BYTES_PER_GRAIN
    if estimated > max_fact_bytes:
        raise CheckpointMemoryLimitError(
            f"Month {month} estimated fact bytes {estimated} exceed limit {max_fact_bytes}"
        )
    uri = database_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        fact = _fact_for_month(connection, month, _read_canonical(_sealed_paths(checkpoint_root, run_id)[0])["supply"]["source_version"])
    finally:
        connection.close()
    if _fact_fingerprint(fact) != entry["fact_fingerprint"]:
        raise CheckpointIntegrityError("Restored month fact fingerprint differs")
    return fact
