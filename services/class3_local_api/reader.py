"""Manifest-verified, fixed-query DuckDB reader for Class 3 serving marts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Final, Iterable

from services.class3_local_api.schemas import ComparisonSelection

import duckdb

from data_pipeline.analysis.class3_serving_mart import (
    MANIFEST_FILENAME,
    SERVING_MART_DATASET_NAME,
    SERVING_MART_SCHEMA_VERSION,
)


_MONTH_PATTERN: Final = re.compile(r"^\d{6}$")
_OUTPUTS: Final[frozenset[str]] = frozenset({
    "product_catalog", "product_month", "item_group_month", "endpoint_composition",
    "endpoint_membership", "coverage",
})
_MART_COLUMNS: Final[dict[str, tuple[str, ...]]] = {
    "product_catalog": ("product_id", "item_group_id", "item_name_id", "source_months"),
    "product_month": ("month", "product_id", "tx_count", "amount_sum_clean", "raw_supply_qty_sum", "piece_qty_sum", "amount_valid_row_count", "raw_supply_qty_valid_row_count", "piece_qty_valid_row_count", "supplier_count_distinct", "receiver_count_distinct", "unique_udi_count_sum", "active_day_count_sum"),
    "item_group_month": ("month", "item_group_id", "tx_count", "amount_sum_clean", "raw_supply_qty_sum", "piece_qty_sum", "amount_valid_row_count", "raw_supply_qty_valid_row_count", "piece_qty_valid_row_count", "supplier_count_distinct", "receiver_count_distinct", "unique_udi_count_sum", "active_day_count_sum"),
    "endpoint_composition": ("month", "product_scope", "product_scope_id", "endpoint", "dimension", "dimension_value", "entity_count_distinct", "tx_count"),
    "endpoint_membership": ("month", "product_scope", "product_scope_id", "parent_item_group_id", "endpoint", "entity_hash", "tx_count"),
    "coverage": ("month", "aggregate_observation_count", "tx_count", "amount_sum_clean", "raw_supply_qty_sum", "piece_qty_sum", "amount_valid_row_count", "raw_supply_qty_valid_row_count", "piece_qty_valid_row_count", "supplier_type_valid_tx_count", "receiver_type_valid_tx_count", "supplier_region_valid_tx_count", "receiver_region_valid_tx_count", "quality_flags", "supplier_type_coverage_ratio", "receiver_type_coverage_ratio", "supplier_region_coverage_ratio", "receiver_region_coverage_ratio"),
}


class MartVerificationError(RuntimeError):
    """Raised before startup when a serving-mart directory is not trustworthy."""


class QueryContractError(ValueError):
    """Raised when a request falls outside the fixed local query contract."""


@dataclass(frozen=True)
class VerifiedMart:
    root: Path
    fingerprint: str
    period_start: str
    period_end: str
    files: dict[str, Path]


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _mart_directory(mart_root: Path) -> Path:
    direct = mart_root / MANIFEST_FILENAME
    if direct.is_file():
        return mart_root
    return mart_root / SERVING_MART_DATASET_NAME / f"schema_version={SERVING_MART_SCHEMA_VERSION}"


def _months(start: str, end: str) -> tuple[str, ...]:
    if not _MONTH_PATTERN.fullmatch(start) or not _MONTH_PATTERN.fullmatch(end):
        raise QueryContractError("period bounds must be YYYYMM")
    year, month = int(start[:4]), int(start[4:])
    finish = (int(end[:4]), int(end[4:]))
    result: list[str] = []
    while (year, month) <= finish:
        if not 1 <= month <= 12:
            raise QueryContractError("period bounds are invalid")
        result.append(f"{year:04d}{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if not result:
        raise QueryContractError("period_start must not be after period_end")
    return tuple(result)


def verify_mart(mart_root: Path) -> VerifiedMart:
    """Validate canonical manifest and every allowlisted materialized file."""
    root = _mart_directory(Path(mart_root))
    manifest_path = root / MANIFEST_FILENAME
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MartVerificationError("serving mart manifest is unreadable") from exc
    if not isinstance(manifest, dict) or raw != _canonical_json_bytes(manifest):
        raise MartVerificationError("serving mart manifest is not canonical")
    required = {
        "serving_mart_dataset_name", "serving_mart_schema_version", "fact_dataset_name",
        "fact_schema_version", "fact_schema_fingerprint", "period_start", "period_end",
        "source_partitions", "output_sha256", "created_fingerprint", "outputs",
    }
    if set(manifest) != required:
        raise MartVerificationError("serving mart manifest fields are invalid")
    if manifest["serving_mart_dataset_name"] != SERVING_MART_DATASET_NAME or manifest["serving_mart_schema_version"] != SERVING_MART_SCHEMA_VERSION:
        raise MartVerificationError("serving mart schema/version is unsupported")
    try:
        period = _months(manifest["period_start"], manifest["period_end"])
    except (KeyError, TypeError, QueryContractError) as exc:
        raise MartVerificationError("serving mart manifest period is invalid") from exc
    fingerprint_input = {key: manifest[key] for key in (
        "serving_mart_dataset_name", "serving_mart_schema_version", "fact_dataset_name",
        "fact_schema_version", "fact_schema_fingerprint", "period_start", "period_end",
        "source_partitions", "output_sha256",
    )}
    if sha256(_canonical_json_bytes(fingerprint_input)).hexdigest() != manifest["created_fingerprint"]:
        raise MartVerificationError("serving mart manifest fingerprint is invalid")
    outputs = manifest["outputs"]
    if not isinstance(outputs, list) or {item.get("name") for item in outputs if isinstance(item, dict)} != _OUTPUTS:
        raise MartVerificationError("serving mart output set is invalid")
    files: dict[str, Path] = {}
    connection = duckdb.connect(database=":memory:")
    try:
        for output in outputs:
            if not isinstance(output, dict) or set(output) != {"name", "filename", "row_count", "sha256"}:
                raise MartVerificationError("serving mart output metadata is invalid")
            name, filename = output["name"], output["filename"]
            if name not in _OUTPUTS or filename != f"{name}.parquet" or Path(filename).name != filename:
                raise MartVerificationError("serving mart output path is invalid")
            path = root / filename
            if not _is_inside(path, root) or not path.is_file():
                raise MartVerificationError("serving mart output is outside root or missing")
            if _sha256_file(path) != output["sha256"] or manifest["output_sha256"].get(name) != output["sha256"]:
                raise MartVerificationError("serving mart output checksum is invalid")
            escaped = path.as_posix().replace("'", "''")
            row_count = int(connection.execute(f"SELECT count(*) FROM read_parquet('{escaped}', hive_partitioning = false)").fetchone()[0])
            if row_count != output["row_count"] or row_count < 0:
                raise MartVerificationError("serving mart output row count is invalid")
            actual_columns = tuple(row[0] for row in connection.execute(f"DESCRIBE SELECT * FROM read_parquet('{escaped}', hive_partitioning = false)").fetchall())
            if actual_columns != _MART_COLUMNS[name]:
                raise MartVerificationError(f"serving mart output schema is invalid: {name}")
            files[name] = path
    except duckdb.Error as exc:
        raise MartVerificationError("serving mart output is unreadable by DuckDB") from exc
    finally:
        connection.close()
    del period
    return VerifiedMart(root, manifest["created_fingerprint"], manifest["period_start"], manifest["period_end"], files)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


class MartReader:
    """Fixed allowlisted read-only query facade over one verified mart."""

    def __init__(self, mart: VerifiedMart) -> None:
        self.mart = mart
        self.connection = duckdb.connect(database=":memory:")

    @classmethod
    def open(cls, mart_root: Path) -> "MartReader":
        return cls(verify_mart(mart_root))

    def close(self) -> None:
        self.connection.close()

    def _table(self, name: str) -> str:
        if name not in _OUTPUTS:
            raise QueryContractError("unknown mart")
        return self.mart.files[name].as_posix().replace("'", "''")

    def _relation(self, name: str) -> str:
        return f"read_parquet('{self._table(name)}', hive_partitioning = false)"

    @staticmethod
    def _columns(name: str) -> str:
        return ", ".join(_MART_COLUMNS[name])

    def _rows(self, sql: str, values: Iterable[Any] = ()) -> list[dict[str, Any]]:
        cursor = self.connection.execute(sql, list(values))
        columns = [item[0] for item in cursor.description]
        return [_json_safe(dict(zip(columns, row, strict=True))) for row in cursor.fetchall()]

    @staticmethod
    def _limit(limit: int | None) -> int:
        value = 20 if limit is None else limit
        if not isinstance(value, int) or value < 1:
            raise QueryContractError("limit must be at least 1")
        return min(value, 50)

    def item_groups(self, query: str | None, limit: int | None) -> list[dict[str, Any]]:
        value = "" if query is None else query.strip()
        if len(value) > 256:
            raise QueryContractError("q is too long")
        return self._rows(
            f"SELECT DISTINCT item_group_id FROM {self._relation('product_catalog')} "
            "WHERE item_group_id IS NOT NULL AND lower(item_group_id) LIKE lower(?) "
            "ORDER BY item_group_id LIMIT ?",
            (f"%{value}%", self._limit(limit)),
        )

    def item_names(self, item_group_id: str, query: str | None, limit: int | None) -> list[dict[str, Any]]:
        if not item_group_id or len(item_group_id) > 512:
            raise QueryContractError("item_group_id is required")
        value = "" if query is None else query.strip()
        return self._rows(
            f"SELECT DISTINCT item_group_id, item_name_id FROM {self._relation('product_catalog')} "
            "WHERE item_group_id = ? AND item_name_id IS NOT NULL AND lower(item_name_id) LIKE lower(?) "
            "ORDER BY item_name_id LIMIT ?",
            (item_group_id, f"%{value}%", self._limit(limit)),
        )

    def comparison(self, period_start: str, period_end: str, selections: list[Any]) -> dict[str, Any]:
        months = _months(period_start, period_end)
        allowed = _months(self.mart.period_start, self.mart.period_end)
        if months[0] not in allowed or months[-1] not in allowed:
            raise QueryContractError("requested period is outside the verified mart range")
        if len(months) > 36:
            raise QueryContractError("requested period must not exceed 36 months")
        if not 1 <= len(selections) <= 10:
            raise QueryContractError("between 1 and 10 selections are required")
        groups = sorted({selection.item_group_id for selection in selections})
        selected_groups = sorted({selection.item_group_id for selection in selections if selection.selection_type == "item_group"})
        item_pairs = sorted({(selection.item_group_id, selection.item_name_id) for selection in selections if selection.selection_type == "item_name"})
        group_placeholders = ",".join("?" for _ in groups)
        pair_predicate = " OR ".join("(item_group_id = ? AND item_name_id = ?)" for _ in item_pairs)
        group_predicate = "item_group_id IN (" + ",".join("?" for _ in selected_groups) + ")" if selected_groups else "FALSE"
        catalog_filter = group_predicate
        values: list[Any] = []
        values.extend(selected_groups)
        if pair_predicate:
            catalog_filter = f"({catalog_filter} OR {pair_predicate})"
            values.extend(value for pair in item_pairs for value in pair)
        catalog = self._rows(
            f"SELECT product_id, item_group_id, item_name_id FROM {self._relation('product_catalog')} WHERE {catalog_filter} ORDER BY product_id",
            values,
        )
        product_ids = sorted({row["product_id"] for row in catalog})
        product_rows: list[dict[str, Any]] = []
        endpoint_rows: list[dict[str, Any]] = []
        if product_ids:
            product_placeholders = ",".join("?" for _ in product_ids)
            product_rows = self._rows(
                f"SELECT {self._columns('product_month')} FROM {self._relation('product_month')} WHERE month BETWEEN ? AND ? AND product_id IN ({product_placeholders}) ORDER BY month, product_id",
                (period_start, period_end, *product_ids),
            )
            endpoint_rows = self._rows(
                f"SELECT {self._columns('endpoint_composition')} FROM {self._relation('endpoint_composition')} WHERE month BETWEEN ? AND ? AND ((product_scope = 'product' AND product_scope_id IN ({product_placeholders})) OR (product_scope = 'item_group' AND product_scope_id IN ({group_placeholders}))) ORDER BY month, product_scope, product_scope_id, endpoint, dimension, dimension_value",
                (period_start, period_end, *product_ids, *groups),
            )
        group_rows = self._rows(
            f"SELECT {self._columns('item_group_month')} FROM {self._relation('item_group_month')} WHERE month BETWEEN ? AND ? AND item_group_id IN ({group_placeholders}) ORDER BY month, item_group_id",
            (period_start, period_end, *groups),
        )
        coverage = self._rows(
            f"SELECT {self._columns('coverage')} FROM {self._relation('coverage')} WHERE month BETWEEN ? AND ? ORDER BY month",
            (period_start, period_end),
        )
        membership = self._membership_rows(period_start, period_end, selections)
        return {
            "period_start": period_start, "period_end": period_end,
            "selections": [selection.model_dump(exclude_none=True) for selection in selections],
            "product_catalog": catalog, "product_month": product_rows,
            "item_group_month": group_rows, "endpoint_composition": endpoint_rows,
            "coverage": coverage,
            "selection_concentration": _selection_concentration(selections, membership),
            "portfolio_overlap": _portfolio_overlap(selections, membership),
        }

    def _membership_rows(
        self, period_start: str, period_end: str, selections: list[ComparisonSelection]
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = [period_start, period_end]
        for selection in selections:
            if selection.selection_type == "item_group":
                clauses.append("(product_scope = 'item_group' AND product_scope_id = ?)")
                values.append(selection.item_group_id)
            else:
                clauses.append(
                    "(product_scope = 'item_name' AND parent_item_group_id = ? AND product_scope_id = ?)"
                )
                values.extend([selection.item_group_id, selection.item_name_id])
        return self._rows(
            f"SELECT {self._columns('endpoint_membership')} FROM {self._relation('endpoint_membership')} "
            f"WHERE month BETWEEN ? AND ? AND ({' OR '.join(clauses)}) "
            "ORDER BY month, product_scope, parent_item_group_id, product_scope_id, endpoint, entity_hash",
            values,
        )


def _selection_ref(selection: ComparisonSelection) -> dict[str, str]:
    if selection.selection_type == "item_name":
        return {
            "selection_type": "item_name",
            "item_group_id": selection.item_group_id,
            "item_name_id": selection.item_name_id or "",
        }
    return {"selection_type": "item_group", "item_group_id": selection.item_group_id}


def _membership_matches(row: dict[str, Any], selection: ComparisonSelection) -> bool:
    if selection.selection_type == "item_group":
        return row.get("product_scope") == "item_group" and row.get("product_scope_id") == selection.item_group_id
    return (
        row.get("product_scope") == "item_name"
        and row.get("parent_item_group_id") == selection.item_group_id
        and row.get("product_scope_id") == selection.item_name_id
    )


def _hhi_string(counts: list[int]) -> str | None:
    total = sum(counts)
    if total <= 0:
        return None
    value = sum((Decimal(count) / Decimal(total)) ** 2 for count in counts)
    return format(value.quantize(Decimal("0.000001")), "f")


def _selection_concentration(
    selections: list[ComparisonSelection], membership: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for selection in selections:
        by_month: dict[str, dict[str, int]] = defaultdict(dict)
        for row in membership:
            if row.get("endpoint") != "supplier" or not _membership_matches(row, selection):
                continue
            month = str(row.get("month") or "")
            entity = str(row.get("entity_hash") or "")
            if not month or not entity:
                continue
            by_month[month][entity] = by_month[month].get(entity, 0) + int(row.get("tx_count") or 0)
        for month in sorted(by_month):
            counts = list(by_month[month].values())
            rows.append({
                **_selection_ref(selection),
                "month": month,
                "supplier_hhi_tx": _hhi_string(counts),
                "market_tx_count": sum(counts),
                "supplier_count": len(counts),
            })
    return rows


def _portfolio_overlap(
    selections: list[ComparisonSelection], membership: list[dict[str, Any]]
) -> dict[str, Any]:
    supplier_sets: list[set[str]] = []
    receiver_sets: list[set[str]] = []
    for selection in selections:
        suppliers: set[str] = set()
        receivers: set[str] = set()
        for row in membership:
            if not _membership_matches(row, selection):
                continue
            entity = str(row.get("entity_hash") or "")
            if not entity:
                continue
            if row.get("endpoint") == "supplier":
                suppliers.add(entity)
            elif row.get("endpoint") == "receiver":
                receivers.add(entity)
        supplier_sets.append(suppliers)
        receiver_sets.append(receivers)
    pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(selections):
        for right_index, right in enumerate(selections):
            if right_index <= left_index:
                continue
            pairs.append({
                "left": _selection_ref(left),
                "right": _selection_ref(right),
                "supplier_intersection_count": len(supplier_sets[left_index] & supplier_sets[right_index]),
                "receiver_intersection_count": len(receiver_sets[left_index] & receiver_sets[right_index]),
            })
    suppliers_union = set().union(*supplier_sets) if supplier_sets else set()
    receivers_union = set().union(*receiver_sets) if receiver_sets else set()
    return {
        "supplier_union_count": len(suppliers_union),
        "receiver_union_count": len(receivers_union),
        "pairs": pairs,
    }
