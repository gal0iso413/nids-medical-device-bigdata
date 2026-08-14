"""Typed, in-memory contract for the Class 3 local analysis data product."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

import pandas as pd


CLASS3_ANALYSIS_SCHEMA_VERSION: Final = "1.0.0"
SELECTION_CATALOG_COLUMNS: Final = (
    "selection_id",
    "selection_type",
    "label",
    "normalized_label",
    "source_labels",
    "parent_item_group_selection_id",
    "parent_item_group_label",
    "parent_conflict_status",
    "quality_flags",
)
SELECTION_MONTH_METRIC_COLUMNS: Final = (
    "selection_id",
    "selection_type",
    "month",
    "tx_count",
    "amount_sum_clean",
    "amount_valid_row_count",
    "amount_coverage",
    "raw_supply_qty_sum",
    "raw_supply_qty_valid_row_count",
    "raw_supply_qty_coverage",
    "piece_qty_sum",
    "piece_qty_valid_row_count",
    "piece_qty_coverage",
    "unique_supplier_count",
    "unique_receiver_count",
    "quality_flags",
)
SELECTION_MONTH_COMPOSITION_COLUMNS: Final = (
    "selection_id",
    "selection_type",
    "month",
    "dimension",
    "dimension_value",
    "is_unknown",
    "endpoint_count",
    "denominator_endpoint_count",
    "endpoint_share",
    "quality_flags",
)
SELECTION_COVERAGE_SUMMARY_COLUMNS: Final = (
    "selection_id",
    "selection_type",
    "period_start",
    "period_end",
    "included_months",
    "missing_months",
    "expected_month_count",
    "included_month_count",
    "missing_month_count",
    "coverage_denominator_tx_count",
    "amount_valid_row_count",
    "amount_valid_rate",
    "raw_supply_qty_valid_row_count",
    "raw_supply_qty_valid_rate",
    "piece_qty_valid_row_count",
    "piece_qty_valid_rate",
    "supplier_endpoint_month_count",
    "receiver_endpoint_month_count",
    "supplier_type_unknown_endpoint_month_count",
    "supplier_type_unknown_rate",
    "receiver_type_unknown_endpoint_month_count",
    "receiver_type_unknown_rate",
    "supplier_region_unknown_endpoint_month_count",
    "supplier_region_unknown_rate",
    "receiver_region_unknown_endpoint_month_count",
    "receiver_region_unknown_rate",
    "source_versions",
    "data_version",
    "fact_schema_version",
    "analysis_schema_version",
    "quality_flags",
)

_STRING_COLUMNS: Final[dict[str, tuple[str, ...]]] = {
    "selection_catalog": tuple(
        column for column in SELECTION_CATALOG_COLUMNS if column not in {"source_labels"}
    ),
    "selection_month_metrics": tuple(
        column
        for column in SELECTION_MONTH_METRIC_COLUMNS
        if column
        not in {
            "tx_count",
            "amount_sum_clean",
            "amount_valid_row_count",
            "amount_coverage",
            "raw_supply_qty_sum",
            "raw_supply_qty_valid_row_count",
            "raw_supply_qty_coverage",
            "piece_qty_sum",
            "piece_qty_valid_row_count",
            "piece_qty_coverage",
            "unique_supplier_count",
            "unique_receiver_count",
        }
    ),
    "selection_month_composition": (
        "selection_id",
        "selection_type",
        "month",
        "dimension",
        "dimension_value",
        "quality_flags",
    ),
    "selection_coverage_summary": tuple(
        column
        for column in SELECTION_COVERAGE_SUMMARY_COLUMNS
        if column
        not in {
            "included_months",
            "missing_months",
            "expected_month_count",
            "included_month_count",
            "missing_month_count",
            "coverage_denominator_tx_count",
            "amount_valid_row_count",
            "amount_valid_rate",
            "raw_supply_qty_valid_row_count",
            "raw_supply_qty_valid_rate",
            "piece_qty_valid_row_count",
            "piece_qty_valid_rate",
            "supplier_endpoint_month_count",
            "receiver_endpoint_month_count",
            "supplier_type_unknown_endpoint_month_count",
            "supplier_type_unknown_rate",
            "receiver_type_unknown_endpoint_month_count",
            "receiver_type_unknown_rate",
            "supplier_region_unknown_endpoint_month_count",
            "supplier_region_unknown_rate",
            "receiver_region_unknown_endpoint_month_count",
            "receiver_region_unknown_rate",
            "source_versions",
        }
    ),
}
_COUNT_COLUMNS: Final[dict[str, tuple[str, ...]]] = {
    "selection_month_metrics": (
        "tx_count",
        "amount_valid_row_count",
        "raw_supply_qty_valid_row_count",
        "piece_qty_valid_row_count",
        "unique_supplier_count",
        "unique_receiver_count",
    ),
    "selection_month_composition": ("endpoint_count", "denominator_endpoint_count"),
    "selection_coverage_summary": (
        "expected_month_count",
        "included_month_count",
        "missing_month_count",
        "coverage_denominator_tx_count",
        "amount_valid_row_count",
        "raw_supply_qty_valid_row_count",
        "piece_qty_valid_row_count",
        "supplier_endpoint_month_count",
        "receiver_endpoint_month_count",
        "supplier_type_unknown_endpoint_month_count",
        "receiver_type_unknown_endpoint_month_count",
        "supplier_region_unknown_endpoint_month_count",
        "receiver_region_unknown_endpoint_month_count",
    ),
}
_DECIMAL_COLUMNS: Final[dict[str, tuple[str, ...]]] = {
    "selection_month_metrics": (
        "amount_sum_clean",
        "amount_coverage",
        "raw_supply_qty_sum",
        "raw_supply_qty_coverage",
        "piece_qty_sum",
        "piece_qty_coverage",
    ),
    "selection_month_composition": ("endpoint_share",),
    "selection_coverage_summary": (
        "amount_valid_rate",
        "raw_supply_qty_valid_rate",
        "piece_qty_valid_rate",
        "supplier_type_unknown_rate",
        "receiver_type_unknown_rate",
        "supplier_region_unknown_rate",
        "receiver_region_unknown_rate",
    ),
}


class Class3AnalysisContractError(ValueError):
    """Raised when a Class 3 analysis table violates its typed contract."""


@dataclass(frozen=True)
class Class3AnalysisTables:
    """All in-memory tables produced by :func:`build_class3_analysis`."""

    selection_catalog: pd.DataFrame
    selection_month_metrics: pd.DataFrame
    selection_month_composition: pd.DataFrame
    selection_coverage_summary: pd.DataFrame


def _empty_table(name: str, columns: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.DataFrame(columns=columns)
    for column in _STRING_COLUMNS[name]:
        frame[column] = frame[column].astype("string")
    for column in _COUNT_COLUMNS.get(name, ()):
        frame[column] = frame[column].astype("Int64")
    if name == "selection_month_composition":
        frame["is_unknown"] = frame["is_unknown"].astype("boolean")
    return frame


def empty_selection_catalog() -> pd.DataFrame:
    return _empty_table("selection_catalog", SELECTION_CATALOG_COLUMNS)


def empty_selection_month_metrics() -> pd.DataFrame:
    return _empty_table("selection_month_metrics", SELECTION_MONTH_METRIC_COLUMNS)


def empty_selection_month_composition() -> pd.DataFrame:
    return _empty_table(
        "selection_month_composition", SELECTION_MONTH_COMPOSITION_COLUMNS
    )


def empty_selection_coverage_summary() -> pd.DataFrame:
    return _empty_table(
        "selection_coverage_summary", SELECTION_COVERAGE_SUMMARY_COLUMNS
    )


def _validate_table(name: str, frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    if tuple(frame.columns) != columns:
        raise Class3AnalysisContractError(f"{name} columns do not match the contract")
    for column in _STRING_COLUMNS[name]:
        if str(frame[column].dtype) != "string":
            raise Class3AnalysisContractError(f"{name}.{column} must use string dtype")
    for column in _COUNT_COLUMNS.get(name, ()):
        if str(frame[column].dtype) != "Int64":
            raise Class3AnalysisContractError(f"{name}.{column} must use Int64 dtype")
    for column in _DECIMAL_COLUMNS.get(name, ()):
        if str(frame[column].dtype) != "object":
            raise Class3AnalysisContractError(f"{name}.{column} must use object Decimal dtype")
    if name == "selection_month_composition" and str(frame["is_unknown"].dtype) != "boolean":
        raise Class3AnalysisContractError("selection_month_composition.is_unknown must use boolean dtype")


def validate_class3_analysis_tables(tables: Class3AnalysisTables) -> Class3AnalysisTables:
    """Validate output shapes and extension dtypes without coercing values."""
    _validate_table("selection_catalog", tables.selection_catalog, SELECTION_CATALOG_COLUMNS)
    _validate_table(
        "selection_month_metrics",
        tables.selection_month_metrics,
        SELECTION_MONTH_METRIC_COLUMNS,
    )
    _validate_table(
        "selection_month_composition",
        tables.selection_month_composition,
        SELECTION_MONTH_COMPOSITION_COLUMNS,
    )
    _validate_table(
        "selection_coverage_summary",
        tables.selection_coverage_summary,
        SELECTION_COVERAGE_SUMMARY_COLUMNS,
    )
    return tables


def _json_value(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if value is None or value is pd.NA:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    if bool(pd.isna(value)):
        return None
    return value


def _table_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {column: _json_value(row[column]) for column in frame.columns}
        for _, row in frame.iterrows()
    ]


def serialize_class3_analysis(tables: Class3AnalysisTables) -> dict[str, Any]:
    """Return a deterministic JSON-compatible representation without writing files."""
    validate_class3_analysis_tables(tables)
    return {
        "analysis_schema_version": CLASS3_ANALYSIS_SCHEMA_VERSION,
        "selection_catalog": _table_records(tables.selection_catalog),
        "selection_month_metrics": _table_records(tables.selection_month_metrics),
        "selection_month_composition": _table_records(
            tables.selection_month_composition
        ),
        "selection_coverage_summary": _table_records(
            tables.selection_coverage_summary
        ),
    }
