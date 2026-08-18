"""Build immutable Class 3 serving marts from verified monthly fact Parquet.

This is a batch materialization boundary, not a query service.  It accepts only
the existing monthly fact store, verifies every selected partition before
reading it, and never writes supplier or receiver identifiers into its output.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from typing import Any, Final, Literal

import pandas as pd

from data_pipeline.contracts.supply_monthly import FACT_SCHEMA_VERSION, MONTHLY_FACT_COLUMNS
from data_pipeline.storage.monthly_fact_parquet import (
    COUNT_COLUMNS,
    DATASET_NAME as FACT_DATASET_NAME,
    DECIMAL_COLUMNS,
    LOGICAL_SCHEMA_FINGERPRINT,
    PartitionVerification,
    read_monthly_fact_partitions,
    verify_monthly_fact_partition,
)


SERVING_MART_SCHEMA_VERSION: Final = "1.1.0"
SERVING_MART_DATASET_NAME: Final = "class3_serving_mart"
MANIFEST_FILENAME: Final = "_manifest.json"
_MONTH_PATTERN: Final = re.compile(r"^\d{6}$")
_ENTITY_HASH_SQL: Final = "hex(sha256(encode({column})))"
_MART_FILENAMES: Final[dict[str, str]] = {
    "product_catalog": "product_catalog.parquet",
    "product_month": "product_month.parquet",
    "item_group_month": "item_group_month.parquet",
    "endpoint_composition": "endpoint_composition.parquet",
    "endpoint_membership": "endpoint_membership.parquet",
    "coverage": "coverage.parquet",
}


class Class3ServingMartError(RuntimeError):
    """Raised when a serving mart cannot be safely built."""


class Class3ServingMartConflictError(Class3ServingMartError):
    """Raised rather than replacing an existing serving mart with new content."""


@dataclass(frozen=True)
class Class3ServingMartResult:
    status: Literal["written", "unchanged"]
    output_path: Path
    manifest_path: Path
    created_fingerprint: str
    row_counts: dict[str, int]


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


def _months(period_start: str, period_end: str) -> tuple[str, ...]:
    if not isinstance(period_start, str) or not isinstance(period_end, str):
        raise Class3ServingMartError("period bounds must be YYYYMM strings")
    if not _MONTH_PATTERN.fullmatch(period_start) or not _MONTH_PATTERN.fullmatch(period_end):
        raise Class3ServingMartError("period bounds must be YYYYMM strings")
    try:
        periods = pd.period_range(period_start, period_end, freq="M")
    except ValueError as exc:
        raise Class3ServingMartError("period bounds are invalid") from exc
    months = tuple(period.strftime("%Y%m") for period in periods)
    if not months or months[0] != period_start or months[-1] != period_end:
        raise Class3ServingMartError("period_start must not be after period_end")
    return months


def _target_dir(output_root: Path) -> Path:
    return output_root / SERVING_MART_DATASET_NAME / f"schema_version={SERVING_MART_SCHEMA_VERSION}"


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _validate_roots(fact_root: Path, output_root: Path, checkpoint_root: Path | None) -> None:
    if not isinstance(fact_root, Path) or not isinstance(output_root, Path):
        raise TypeError("fact_root and output_root must be pathlib.Path values")
    if _is_within(output_root, fact_root) or _is_within(fact_root, output_root):
        raise Class3ServingMartError("output_root must not overlap fact_root")
    if checkpoint_root is not None and (
        _is_within(output_root, checkpoint_root) or _is_within(checkpoint_root, output_root)
    ):
        raise Class3ServingMartError("output_root must not overlap checkpoint_root")


def _duckdb_connection() -> Any:
    try:
        import duckdb
    except ImportError as exc:
        raise Class3ServingMartError(
            "DuckDB is required; install the approved serving-mart offline wheel"
        ) from exc
    return duckdb.connect(database=":memory:")


def _copy_query(connection: Any, query: str, path: Path) -> None:
    # DuckDB parameters do not bind output file names.  The generated staging
    # name is private and never enters a manifest or diagnostic.
    escaped = path.as_posix().replace("'", "''")
    connection.execute(
        f"COPY ({query}) TO '{escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def _build_queries() -> dict[str, str]:
    valid = {
        "amount": "amount_valid_row_count",
        "raw_supply_qty": "raw_supply_qty_valid_row_count",
        "piece_qty": "piece_qty_valid_row_count",
    }
    product_month = """
        SELECT
          month, product_id,
          SUM(tx_count) AS tx_count,
          SUM(amount_sum_clean) AS amount_sum_clean,
          SUM(raw_supply_qty_sum) AS raw_supply_qty_sum,
          SUM(piece_qty_sum) AS piece_qty_sum,
          SUM(amount_valid_row_count) AS amount_valid_row_count,
          SUM(raw_supply_qty_valid_row_count) AS raw_supply_qty_valid_row_count,
          SUM(piece_qty_valid_row_count) AS piece_qty_valid_row_count,
          COUNT(DISTINCT src_company_id) AS supplier_count_distinct,
          COUNT(DISTINCT dst_company_id) AS receiver_count_distinct,
          SUM(unique_udi_count) AS unique_udi_count_sum,
          SUM(active_day_count) AS active_day_count_sum
        FROM fact
        GROUP BY month, product_id
        ORDER BY month, product_id
    """
    item_group_month = """
        SELECT
          month, item_group_id,
          SUM(tx_count) AS tx_count,
          SUM(amount_sum_clean) AS amount_sum_clean,
          SUM(raw_supply_qty_sum) AS raw_supply_qty_sum,
          SUM(piece_qty_sum) AS piece_qty_sum,
          SUM(amount_valid_row_count) AS amount_valid_row_count,
          SUM(raw_supply_qty_valid_row_count) AS raw_supply_qty_valid_row_count,
          SUM(piece_qty_valid_row_count) AS piece_qty_valid_row_count,
          COUNT(DISTINCT src_company_id) AS supplier_count_distinct,
          COUNT(DISTINCT dst_company_id) AS receiver_count_distinct,
          SUM(unique_udi_count) AS unique_udi_count_sum,
          SUM(active_day_count) AS active_day_count_sum
        FROM fact
        GROUP BY month, item_group_id
        ORDER BY month, item_group_id
    """
    endpoint_composition = """
        SELECT month, 'product' AS product_scope, product_id AS product_scope_id,
               'supplier' AS endpoint, 'type' AS dimension, supplier_type AS dimension_value,
               COUNT(DISTINCT src_company_id) AS entity_count_distinct,
               SUM(tx_count) AS tx_count
          FROM fact WHERE supplier_type IS NOT NULL AND trim(supplier_type) <> ''
          GROUP BY month, product_id, supplier_type
        UNION ALL
        SELECT month, 'product', product_id, 'supplier', 'region', supplier_region,
               COUNT(DISTINCT src_company_id), SUM(tx_count)
          FROM fact WHERE supplier_region IS NOT NULL AND trim(supplier_region) <> ''
          GROUP BY month, product_id, supplier_region
        UNION ALL
        SELECT month, 'product', product_id, 'receiver', 'type', receiver_type,
               COUNT(DISTINCT dst_company_id), SUM(tx_count)
          FROM fact WHERE receiver_type IS NOT NULL AND trim(receiver_type) <> ''
          GROUP BY month, product_id, receiver_type
        UNION ALL
        SELECT month, 'product', product_id, 'receiver', 'region', receiver_region,
               COUNT(DISTINCT dst_company_id), SUM(tx_count)
          FROM fact WHERE receiver_region IS NOT NULL AND trim(receiver_region) <> ''
          GROUP BY month, product_id, receiver_region
        UNION ALL
        SELECT month, 'item_group', item_group_id, 'supplier', 'type', supplier_type,
               COUNT(DISTINCT src_company_id), SUM(tx_count)
          FROM fact WHERE item_group_id IS NOT NULL AND trim(item_group_id) <> ''
                    AND supplier_type IS NOT NULL AND trim(supplier_type) <> ''
          GROUP BY month, item_group_id, supplier_type
        UNION ALL
        SELECT month, 'item_group', item_group_id, 'supplier', 'region', supplier_region,
               COUNT(DISTINCT src_company_id), SUM(tx_count)
          FROM fact WHERE item_group_id IS NOT NULL AND trim(item_group_id) <> ''
                    AND supplier_region IS NOT NULL AND trim(supplier_region) <> ''
          GROUP BY month, item_group_id, supplier_region
        UNION ALL
        SELECT month, 'item_group', item_group_id, 'receiver', 'type', receiver_type,
               COUNT(DISTINCT dst_company_id), SUM(tx_count)
          FROM fact WHERE item_group_id IS NOT NULL AND trim(item_group_id) <> ''
                    AND receiver_type IS NOT NULL AND trim(receiver_type) <> ''
          GROUP BY month, item_group_id, receiver_type
        UNION ALL
        SELECT month, 'item_group', item_group_id, 'receiver', 'region', receiver_region,
               COUNT(DISTINCT dst_company_id), SUM(tx_count)
          FROM fact WHERE item_group_id IS NOT NULL AND trim(item_group_id) <> ''
                    AND receiver_region IS NOT NULL AND trim(receiver_region) <> ''
          GROUP BY month, item_group_id, receiver_region
        ORDER BY month, product_scope, product_scope_id, endpoint, dimension, dimension_value
    """
    supplier_hash = _ENTITY_HASH_SQL.format(column="src_company_id")
    receiver_hash = _ENTITY_HASH_SQL.format(column="dst_company_id")
    endpoint_membership = f"""
        SELECT month, 'item_group' AS product_scope, item_group_id AS product_scope_id,
               CAST(NULL AS VARCHAR) AS parent_item_group_id, 'supplier' AS endpoint,
               {supplier_hash} AS entity_hash, SUM(tx_count) AS tx_count
          FROM fact
          WHERE item_group_id IS NOT NULL AND trim(item_group_id) <> ''
            AND src_company_id IS NOT NULL AND trim(src_company_id) <> ''
          GROUP BY month, item_group_id, src_company_id
        UNION ALL
        SELECT month, 'item_group', item_group_id, CAST(NULL AS VARCHAR), 'receiver',
               {receiver_hash}, SUM(tx_count)
          FROM fact
          WHERE item_group_id IS NOT NULL AND trim(item_group_id) <> ''
            AND dst_company_id IS NOT NULL AND trim(dst_company_id) <> ''
          GROUP BY month, item_group_id, dst_company_id
        UNION ALL
        SELECT month, 'item_name', item_name_id, item_group_id, 'supplier',
               {supplier_hash}, SUM(tx_count)
          FROM fact
          WHERE item_group_id IS NOT NULL AND trim(item_group_id) <> ''
            AND item_name_id IS NOT NULL AND trim(item_name_id) <> ''
            AND src_company_id IS NOT NULL AND trim(src_company_id) <> ''
          GROUP BY month, item_group_id, item_name_id, src_company_id
        UNION ALL
        SELECT month, 'item_name', item_name_id, item_group_id, 'receiver',
               {receiver_hash}, SUM(tx_count)
          FROM fact
          WHERE item_group_id IS NOT NULL AND trim(item_group_id) <> ''
            AND item_name_id IS NOT NULL AND trim(item_name_id) <> ''
            AND dst_company_id IS NOT NULL AND trim(dst_company_id) <> ''
          GROUP BY month, item_group_id, item_name_id, dst_company_id
        ORDER BY month, product_scope, parent_item_group_id, product_scope_id, endpoint, entity_hash
    """
    coverage_columns = ",\n          ".join(
        f"SUM(CASE WHEN {column} IS NOT NULL AND trim({column}) <> '' THEN tx_count ELSE 0 END) AS {name}_valid_tx_count"
        for name, column in (
            ("supplier_type", "supplier_type"),
            ("receiver_type", "receiver_type"),
            ("supplier_region", "supplier_region"),
            ("receiver_region", "receiver_region"),
        )
    )
    coverage = f"""
        WITH monthly_coverage AS (
        SELECT
          month,
          COUNT(*) AS aggregate_observation_count,
          SUM(tx_count) AS tx_count,
          SUM(amount_sum_clean) AS amount_sum_clean,
          SUM(raw_supply_qty_sum) AS raw_supply_qty_sum,
          SUM(piece_qty_sum) AS piece_qty_sum,
          SUM(amount_valid_row_count) AS amount_valid_row_count,
          SUM(raw_supply_qty_valid_row_count) AS raw_supply_qty_valid_row_count,
          SUM(piece_qty_valid_row_count) AS piece_qty_valid_row_count,
          {coverage_columns},
          string_agg(DISTINCT NULLIF(quality_flags, ''), ';' ORDER BY NULLIF(quality_flags, '')) AS quality_flags
        FROM fact
        GROUP BY month
        )
        SELECT *,
          CAST(supplier_type_valid_tx_count AS DOUBLE) / NULLIF(tx_count, 0) AS supplier_type_coverage_ratio,
          CAST(receiver_type_valid_tx_count AS DOUBLE) / NULLIF(tx_count, 0) AS receiver_type_coverage_ratio,
          CAST(supplier_region_valid_tx_count AS DOUBLE) / NULLIF(tx_count, 0) AS supplier_region_coverage_ratio,
          CAST(receiver_region_valid_tx_count AS DOUBLE) / NULLIF(tx_count, 0) AS receiver_region_coverage_ratio
        FROM monthly_coverage
        ORDER BY month
    """
    del valid  # The valid-row columns are explicitly retained in both additive marts.
    return {
        "product_catalog": """
            SELECT product_id, item_group_id, item_name_id,
                   string_agg(DISTINCT month, ',' ORDER BY month) AS source_months
            FROM fact
            GROUP BY product_id, item_group_id, item_name_id
            ORDER BY product_id, item_group_id, item_name_id
        """,
        "product_month": product_month,
        "item_group_month": item_group_month,
        "endpoint_composition": endpoint_composition,
        "endpoint_membership": endpoint_membership,
        "coverage": coverage,
    }


def _source_lineage(verifications: tuple[PartitionVerification, ...]) -> list[dict[str, Any]]:
    return [
        {
            "month": item.month,
            "partition_name": item.relative_parquet_path,
            "parquet_sha256": item.parquet_sha256,
            "row_count": item.row_count,
        }
        for item in verifications
    ]


def _fact_table_sql() -> str:
    columns: list[str] = []
    for name in MONTHLY_FACT_COLUMNS:
        if name in DECIMAL_COLUMNS:
            columns.append(f"{name} DECIMAL(38,6)")
        elif name in COUNT_COLUMNS:
            columns.append(f"{name} BIGINT")
        else:
            columns.append(f"{name} VARCHAR")
    return "CREATE TABLE fact (" + ", ".join(columns) + ")"


def _write_candidate(
    staging: Path, fact_root: Path, months: tuple[str, ...]
) -> tuple[dict[str, int], dict[str, str]]:
    connection = _duckdb_connection()
    try:
        connection.execute(_fact_table_sql())
        for month in months:
            frame = read_monthly_fact_partitions(fact_root, months=(month,))
            if frame.empty:
                raise Class3ServingMartError(f"verified partition {month} has no aggregate observations")
            loaded = frame.copy()
            for column in DECIMAL_COLUMNS:
                loaded[column] = loaded[column].map(
                    lambda value: None if value is None or pd.isna(value) else format(value, "f")
                )
            connection.register("monthly_frame", loaded)
            columns = ", ".join(MONTHLY_FACT_COLUMNS)
            selects = ", ".join(
                f"CAST({name} AS DECIMAL(38,6))" if name in DECIMAL_COLUMNS else name
                for name in MONTHLY_FACT_COLUMNS
            )
            connection.execute(f"INSERT INTO fact ({columns}) SELECT {selects} FROM monthly_frame")
            connection.unregister("monthly_frame")
        row_counts: dict[str, int] = {}
        hashes: dict[str, str] = {}
        for name, query in _build_queries().items():
            output_path = staging / _MART_FILENAMES[name]
            _copy_query(connection, query, output_path)
            row_counts[name] = int(connection.execute(f"SELECT count(*) FROM ({query})").fetchone()[0])
            hashes[name] = _sha256_file(output_path)
        return row_counts, hashes
    except Class3ServingMartError:
        raise
    except Exception as exc:
        raise Class3ServingMartError("could not build Class 3 serving marts") from exc
    finally:
        connection.close()


def _candidate_manifest(
    *, period_start: str, period_end: str, verifications: tuple[PartitionVerification, ...],
    row_counts: dict[str, int], hashes: dict[str, str],
) -> dict[str, Any]:
    source_partitions = _source_lineage(verifications)
    fingerprint_input = {
        "serving_mart_dataset_name": SERVING_MART_DATASET_NAME,
        "serving_mart_schema_version": SERVING_MART_SCHEMA_VERSION,
        "fact_dataset_name": FACT_DATASET_NAME,
        "fact_schema_version": FACT_SCHEMA_VERSION,
        "fact_schema_fingerprint": LOGICAL_SCHEMA_FINGERPRINT,
        "period_start": period_start,
        "period_end": period_end,
        "source_partitions": source_partitions,
        "output_sha256": hashes,
    }
    return {
        **fingerprint_input,
        "created_fingerprint": _fingerprint(fingerprint_input),
        "outputs": [
            {
                "name": name,
                "filename": _MART_FILENAMES[name],
                "row_count": row_counts[name],
                "sha256": hashes[name],
            }
            for name in sorted(_MART_FILENAMES)
        ],
    }


def _read_existing_manifest(final_dir: Path) -> dict[str, Any]:
    path = final_dir / MANIFEST_FILENAME
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Class3ServingMartConflictError("existing serving mart manifest is unreadable") from exc
    if not isinstance(value, dict) or raw != _canonical_json_bytes(value):
        raise Class3ServingMartConflictError("existing serving mart manifest is not canonical")
    return value


def _existing_matches(final_dir: Path, candidate: dict[str, Any]) -> bool:
    existing = _read_existing_manifest(final_dir)
    if existing.get("created_fingerprint") != candidate["created_fingerprint"]:
        return False
    if existing != candidate:
        return False
    for output in candidate["outputs"]:
        path = final_dir / output["filename"]
        if not path.is_file() or _sha256_file(path) != output["sha256"]:
            return False
    return True


def _new_staging_dir(final_dir: Path) -> Path:
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        candidate = final_dir.parent / f".{final_dir.name}.tmp-{secrets.token_hex(8)}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise Class3ServingMartError("could not allocate serving mart staging directory")


def build_class3_serving_marts(
    *,
    fact_root: Path,
    output_root: Path,
    period_start: str,
    period_end: str,
    checkpoint_root: Path | None = None,
) -> Class3ServingMartResult:
    """Materialize a period's immutable serving marts from verified fact partitions."""
    _validate_roots(fact_root, output_root, checkpoint_root)
    months = _months(period_start, period_end)
    try:
        verifications = tuple(verify_monthly_fact_partition(fact_root, month) for month in months)
    except Exception as exc:
        raise Class3ServingMartError("all requested monthly fact partitions must verify") from exc
    final_dir = _target_dir(output_root)
    staging = _new_staging_dir(final_dir)
    try:
        row_counts, hashes = _write_candidate(staging, fact_root, months)
        candidate = _candidate_manifest(
            period_start=period_start, period_end=period_end, verifications=verifications,
            row_counts=row_counts, hashes=hashes,
        )
        (staging / MANIFEST_FILENAME).write_bytes(_canonical_json_bytes(candidate))
        if final_dir.exists():
            if _existing_matches(final_dir, candidate):
                return Class3ServingMartResult(
                    "unchanged", final_dir, final_dir / MANIFEST_FILENAME,
                    str(candidate["created_fingerprint"]), row_counts,
                )
            raise Class3ServingMartConflictError(
                "serving mart output already exists with different content"
            )
        try:
            staging.replace(final_dir)
        except OSError as exc:
            if final_dir.exists() and _existing_matches(final_dir, candidate):
                return Class3ServingMartResult(
                    "unchanged", final_dir, final_dir / MANIFEST_FILENAME,
                    str(candidate["created_fingerprint"]), row_counts,
                )
            raise Class3ServingMartError("could not atomically publish serving marts") from exc
        return Class3ServingMartResult(
            "written", final_dir, final_dir / MANIFEST_FILENAME,
            str(candidate["created_fingerprint"]), row_counts,
        )
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Class 3 serving marts from verified monthly facts.")
    parser.add_argument("--fact-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--period-start", required=True)
    parser.add_argument("--period-end", required=True)
    parser.add_argument("--checkpoint-root", type=Path)
    args = parser.parse_args(argv)
    result = build_class3_serving_marts(
        fact_root=args.fact_root, output_root=args.output_root,
        period_start=args.period_start, period_end=args.period_end,
        checkpoint_root=args.checkpoint_root,
    )
    print(_canonical_json_bytes({
        "status": result.status,
        "created_fingerprint": result.created_fingerprint,
        "row_counts": result.row_counts,
    }).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
