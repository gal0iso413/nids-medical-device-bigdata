"""Pure Class 3 analysis tables derived from the shared monthly fact."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from hashlib import sha256
import re
import unicodedata
from typing import Any, Final

import pandas as pd

from data_pipeline.contracts.class3_analysis import (
    CLASS3_ANALYSIS_SCHEMA_VERSION,
    Class3AnalysisContractError,
    Class3AnalysisTables,
    SELECTION_COVERAGE_SUMMARY_COLUMNS,
    empty_selection_catalog,
    empty_selection_coverage_summary,
    empty_selection_month_composition,
    empty_selection_month_metrics,
    validate_class3_analysis_tables,
)
from data_pipeline.contracts.supply_monthly import (
    FACT_SCHEMA_VERSION,
    validate_monthly_fact,
)


_MONTH_PATTERN: Final = re.compile(r"^\d{6}$")
_WHITESPACE_PATTERN: Final = re.compile(r"\s+")
_COVERAGE_QUANTUM: Final = Decimal("0.000001")
_UNKNOWN_PARENT: Final = "<unknown-parent>"
_DIMENSIONS: Final[tuple[tuple[str, str], ...]] = (
    ("supplier_type", "src_company_id"),
    ("receiver_type", "dst_company_id"),
    ("supplier_region", "src_company_id"),
    ("receiver_region", "dst_company_id"),
)


def _is_missing(value: Any) -> bool:
    return value is None or value is pd.NA or bool(pd.isna(value))


def _clean_label(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def _normalize_label(value: Any) -> str | None:
    label = _clean_label(value)
    if label is None:
        return None
    return _WHITESPACE_PATTERN.sub(" ", unicodedata.normalize("NFKC", label)).casefold()


def _selection_id(selection_type: str, normalized_label: str, parent_id: str = "") -> str:
    payload = f"{selection_type}\0{normalized_label}\0{parent_id}".encode("utf-8")
    return f"c3s:v1:{selection_type}:{sha256(payload).hexdigest()}"


def _month_range(period_start: str, period_end: str) -> tuple[str, ...]:
    if not isinstance(period_start, str) or not isinstance(period_end, str):
        raise Class3AnalysisContractError("period bounds must be YYYYMM strings")
    if not _MONTH_PATTERN.fullmatch(period_start) or not _MONTH_PATTERN.fullmatch(period_end):
        raise Class3AnalysisContractError("period bounds must be YYYYMM strings")
    try:
        months = pd.period_range(period_start, period_end, freq="M")
    except ValueError as exc:
        raise Class3AnalysisContractError("period bounds are invalid") from exc
    if not len(months):
        raise Class3AnalysisContractError("period bounds are invalid")
    return tuple(period.strftime("%Y%m") for period in months)


def _coverage(numerator: int, denominator: int) -> Decimal | Any:
    if denominator == 0:
        return pd.NA
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        _COVERAGE_QUANTUM, rounding=ROUND_HALF_EVEN
    )


def _decimal_sum(values: pd.Series) -> Decimal | Any:
    total = Decimal("0")
    found = False
    for value in values:
        if not _is_missing(value):
            if not isinstance(value, Decimal):
                raise Class3AnalysisContractError("monthly fact decimals must remain Decimal")
            total += value
            found = True
    return total if found else pd.NA


def _merged_flags(values: pd.Series) -> str:
    flags: set[str] = set()
    for value in values:
        if _is_missing(value):
            continue
        flags.update(flag for flag in str(value).split(";") if flag)
    return ";".join(sorted(flags))


def _catalog_and_membership(fact: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    entries: list[dict[str, Any]] = []
    membership: list[dict[str, Any]] = []
    group_labels: dict[str, set[str]] = {}
    name_parents: dict[str, set[str]] = {}
    name_labels: dict[tuple[str, str], set[str]] = {}

    for position, row in fact.reset_index(drop=True).iterrows():
        group_label = _clean_label(row["item_group_id"])
        group_normalized = _normalize_label(row["item_group_id"])
        name_label = _clean_label(row["item_name_id"])
        name_normalized = _normalize_label(row["item_name_id"])
        if group_normalized is not None and group_label is not None:
            group_labels.setdefault(group_normalized, set()).add(group_label)
        if name_normalized is not None and name_label is not None:
            parent = group_normalized if group_normalized is not None else _UNKNOWN_PARENT
            name_parents.setdefault(name_normalized, set()).add(parent)
            name_labels.setdefault((name_normalized, parent), set()).add(name_label)

    group_ids = {
        normalized: _selection_id("item_group", normalized)
        for normalized in sorted(group_labels)
    }
    for normalized, selection_id in group_ids.items():
        labels = tuple(sorted(group_labels[normalized]))
        entries.append(
            {
                "selection_id": selection_id,
                "selection_type": "item_group",
                "label": labels[0],
                "normalized_label": normalized,
                "source_labels": labels,
                "parent_item_group_selection_id": pd.NA,
                "parent_item_group_label": pd.NA,
                "parent_conflict_status": "not_applicable",
                "quality_flags": "normalized_label_collision" if len(labels) > 1 else "",
            }
        )

    name_ids: dict[tuple[str, str], str] = {}
    for name_normalized, parents in name_parents.items():
        for parent in sorted(parents):
            parent_id = "" if parent == _UNKNOWN_PARENT else group_ids[parent]
            name_ids[(name_normalized, parent)] = _selection_id(
                "item_name", name_normalized, parent_id or _UNKNOWN_PARENT
            )

    for (name_normalized, parent), selection_id in sorted(name_ids.items()):
        labels = tuple(sorted(name_labels[(name_normalized, parent)]))
        parents = name_parents[name_normalized]
        known_parent_count = len(parents - {_UNKNOWN_PARENT})
        if known_parent_count > 1:
            parent_status = "multiple"
        elif _UNKNOWN_PARENT in parents:
            parent_status = "missing"
        else:
            parent_status = "none"
        parent_id = pd.NA if parent == _UNKNOWN_PARENT else group_ids[parent]
        parent_label = pd.NA
        if parent != _UNKNOWN_PARENT:
            parent_label = tuple(sorted(group_labels[parent]))[0]
        flags = ["normalized_label_collision"] if len(labels) > 1 else []
        entries.append(
            {
                "selection_id": selection_id,
                "selection_type": "item_name",
                "label": labels[0],
                "normalized_label": name_normalized,
                "source_labels": labels,
                "parent_item_group_selection_id": parent_id,
                "parent_item_group_label": parent_label,
                "parent_conflict_status": parent_status,
                "quality_flags": ";".join(flags),
            }
        )

    for position, row in fact.reset_index(drop=True).iterrows():
        group_normalized = _normalize_label(row["item_group_id"])
        name_normalized = _normalize_label(row["item_name_id"])
        if group_normalized is not None:
            membership.append(
                {
                    "fact_position": position,
                    "selection_id": group_ids[group_normalized],
                    "selection_type": "item_group",
                }
            )
        if name_normalized is not None:
            parent = group_normalized if group_normalized is not None else _UNKNOWN_PARENT
            membership.append(
                {
                    "fact_position": position,
                    "selection_id": name_ids[(name_normalized, parent)],
                    "selection_type": "item_name",
                }
            )

    if not entries:
        return empty_selection_catalog(), pd.DataFrame(
            columns=("fact_position", "selection_id", "selection_type")
        )
    catalog = pd.DataFrame(entries).sort_values(
        ["selection_type", "selection_id"], kind="stable"
    ).reset_index(drop=True)
    for column in catalog.columns:
        if column != "source_labels":
            catalog[column] = catalog[column].astype("string")
    return catalog, pd.DataFrame(membership)


def _typed_metrics(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return empty_selection_month_metrics()
    frame = pd.DataFrame(records).sort_values(
        ["selection_id", "month"], kind="stable"
    ).reset_index(drop=True)
    for column in (
        "selection_id", "selection_type", "month", "quality_flags"
    ):
        frame[column] = frame[column].astype("string")
    for column in (
        "tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count",
        "piece_qty_valid_row_count", "unique_supplier_count", "unique_receiver_count",
    ):
        frame[column] = frame[column].astype("Int64")
    return frame


def _build_metrics(members: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    if members.empty:
        return empty_selection_month_metrics()
    grouped = members.groupby(["selection_id", "selection_type", "month"], sort=True)
    for (selection_id, selection_type, month), group in grouped:
        tx_count = int(group["tx_count"].sum())
        amount_valid = int(group["amount_valid_row_count"].sum())
        raw_valid = int(group["raw_supply_qty_valid_row_count"].sum())
        piece_valid = int(group["piece_qty_valid_row_count"].sum())
        records.append(
            {
                "selection_id": selection_id,
                "selection_type": selection_type,
                "month": month,
                "tx_count": tx_count,
                "amount_sum_clean": _decimal_sum(group["amount_sum_clean"]),
                "amount_valid_row_count": amount_valid,
                "amount_coverage": _coverage(amount_valid, tx_count),
                "raw_supply_qty_sum": _decimal_sum(group["raw_supply_qty_sum"]),
                "raw_supply_qty_valid_row_count": raw_valid,
                "raw_supply_qty_coverage": _coverage(raw_valid, tx_count),
                "piece_qty_sum": _decimal_sum(group["piece_qty_sum"]),
                "piece_qty_valid_row_count": piece_valid,
                "piece_qty_coverage": _coverage(piece_valid, tx_count),
                "unique_supplier_count": int(group["src_company_id"].nunique()),
                "unique_receiver_count": int(group["dst_company_id"].nunique()),
                "quality_flags": _merged_flags(group["quality_flags"]),
            }
        )
    return _typed_metrics(records)


def _typed_composition(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return empty_selection_month_composition()
    frame = pd.DataFrame(records).sort_values(
        ["selection_id", "month", "dimension", "is_unknown", "dimension_value"],
        kind="stable",
    ).reset_index(drop=True)
    for column in (
        "selection_id", "selection_type", "month", "dimension", "dimension_value", "quality_flags"
    ):
        frame[column] = frame[column].astype("string")
    frame["is_unknown"] = frame["is_unknown"].astype("boolean")
    for column in ("endpoint_count", "denominator_endpoint_count"):
        frame[column] = frame[column].astype("Int64")
    return frame


def _build_composition(members: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    if members.empty:
        return empty_selection_month_composition()
    for dimension, endpoint_column in _DIMENSIONS:
        endpoint_records: list[dict[str, Any]] = []
        grouped = members.groupby(["selection_id", "selection_type", "month", endpoint_column], sort=True)
        for key, group in grouped:
            selection_id, selection_type, month, _endpoint = key
            values = {_clean_label(value) for value in group[dimension]}
            values.discard(None)
            flags = _merged_flags(group["quality_flags"]).split(";")
            flagged = f"{dimension}_missing" in flags or f"{dimension}_conflict" in flags
            unknown = flagged or len(values) != 1
            endpoint_records.append(
                {
                    "selection_id": selection_id,
                    "selection_type": selection_type,
                    "month": month,
                    "dimension": dimension,
                    "dimension_value": "unknown" if unknown else next(iter(values)),
                    "is_unknown": unknown,
                }
            )
        endpoints = pd.DataFrame(endpoint_records)
        if endpoints.empty:
            continue
        denominators = endpoints.groupby(
            ["selection_id", "selection_type", "month", "dimension"], sort=True
        ).size()
        counted = endpoints.groupby(
            [
                "selection_id", "selection_type", "month", "dimension",
                "dimension_value", "is_unknown",
            ],
            sort=True,
            dropna=False,
        ).size()
        for key, count in counted.items():
            selection_id, selection_type, month, dim, value, unknown = key
            denominator = int(denominators[(selection_id, selection_type, month, dim)])
            records.append(
                {
                    "selection_id": selection_id,
                    "selection_type": selection_type,
                    "month": month,
                    "dimension": dim,
                    "dimension_value": value,
                    "is_unknown": bool(unknown),
                    "endpoint_count": int(count),
                    "denominator_endpoint_count": denominator,
                    "endpoint_share": _coverage(int(count), denominator),
                    "quality_flags": "dimension_unknown" if unknown else "",
                }
            )
    composition = _typed_composition(records)
    if not composition.empty:
        grouped = composition.groupby(
            ["selection_id", "selection_type", "month", "dimension"], sort=True
        )
        for _, group in grouped:
            if int(group["endpoint_count"].sum()) != int(group["denominator_endpoint_count"].iloc[0]):
                raise Class3AnalysisContractError("composition denominator invariant failed")
    return composition


def _typed_coverage(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return empty_selection_coverage_summary()
    frame = pd.DataFrame(records).loc[:, SELECTION_COVERAGE_SUMMARY_COLUMNS]
    frame = frame.sort_values("selection_id", kind="stable").reset_index(drop=True)
    tuple_columns = {"included_months", "missing_months", "source_versions"}
    decimal_columns = {
        "amount_valid_rate", "raw_supply_qty_valid_rate", "piece_qty_valid_rate",
        "supplier_type_unknown_rate", "receiver_type_unknown_rate",
        "supplier_region_unknown_rate", "receiver_region_unknown_rate",
    }
    count_columns = {
        "expected_month_count", "included_month_count", "missing_month_count",
        "coverage_denominator_tx_count", "amount_valid_row_count",
        "raw_supply_qty_valid_row_count", "piece_qty_valid_row_count",
        "supplier_endpoint_month_count", "receiver_endpoint_month_count",
        "supplier_type_unknown_endpoint_month_count",
        "receiver_type_unknown_endpoint_month_count",
        "supplier_region_unknown_endpoint_month_count",
        "receiver_region_unknown_endpoint_month_count",
    }
    for column in frame.columns:
        if column not in tuple_columns and column not in count_columns and column not in decimal_columns:
            frame[column] = frame[column].astype("string")
    for column in count_columns:
        frame[column] = frame[column].astype("Int64")
    return frame


def _build_coverage(
    catalog: pd.DataFrame,
    members: pd.DataFrame,
    metrics: pd.DataFrame,
    composition: pd.DataFrame,
    months: tuple[str, ...],
    data_version: str,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for catalog_row in catalog.itertuples(index=False):
        selection_id = catalog_row.selection_id
        selection_type = catalog_row.selection_type
        metric_rows = metrics.loc[metrics["selection_id"].eq(selection_id)]
        included = tuple(metric_rows["month"].astype(str).tolist())
        missing = tuple(month for month in months if month not in set(included))
        total_tx = int(metric_rows["tx_count"].sum()) if not metric_rows.empty else 0
        member_rows = members.loc[members["selection_id"].eq(selection_id)]
        source_versions = tuple(sorted(member_rows["source_version"].dropna().astype(str).unique()))
        flags = ["no_included_months"] if not included else []
        record: dict[str, Any] = {
            "selection_id": selection_id,
            "selection_type": selection_type,
            "period_start": months[0],
            "period_end": months[-1],
            "included_months": included,
            "missing_months": missing,
            "expected_month_count": len(months),
            "included_month_count": len(included),
            "missing_month_count": len(missing),
            "coverage_denominator_tx_count": total_tx,
            "source_versions": source_versions,
            "data_version": data_version,
            "fact_schema_version": FACT_SCHEMA_VERSION,
            "analysis_schema_version": CLASS3_ANALYSIS_SCHEMA_VERSION,
            "quality_flags": ";".join(flags),
        }
        for prefix in ("amount", "raw_supply_qty", "piece_qty"):
            valid_column = f"{prefix}_valid_row_count"
            valid_count = int(metric_rows[valid_column].sum()) if not metric_rows.empty else 0
            record[valid_column] = valid_count
            record[f"{prefix}_valid_rate"] = _coverage(valid_count, total_tx)
        for dimension, endpoint_column in _DIMENSIONS:
            rows = composition.loc[
                (composition["selection_id"].eq(selection_id))
                & (composition["dimension"].eq(dimension))
            ]
            unique_monthly = rows.drop_duplicates("month") if not rows.empty else rows
            denominator = int(unique_monthly["denominator_endpoint_count"].sum()) if not rows.empty else 0
            unknown_count = int(rows.loc[rows["is_unknown"], "endpoint_count"].sum()) if not rows.empty else 0
            side = "supplier" if endpoint_column == "src_company_id" else "receiver"
            if dimension.endswith("_type"):
                record[f"{side}_endpoint_month_count"] = denominator
            record[f"{dimension}_unknown_endpoint_month_count"] = unknown_count
            record[f"{dimension}_unknown_rate"] = _coverage(unknown_count, denominator)
        records.append(record)
    return _typed_coverage(records)


def build_class3_analysis(
    fact: pd.DataFrame,
    *,
    period_start: str,
    period_end: str,
    data_version: str,
) -> Class3AnalysisTables:
    """Build deterministic Class 3 local analysis tables from a monthly fact."""
    validated = validate_monthly_fact(fact)
    months = _month_range(period_start, period_end)
    if not isinstance(data_version, str):
        raise Class3AnalysisContractError("data_version must be a non-blank string")
    normalized_data_version = _clean_label(data_version)
    if normalized_data_version is None:
        raise Class3AnalysisContractError("data_version is required")

    catalog, membership = _catalog_and_membership(validated)
    if membership.empty:
        members = pd.DataFrame()
    else:
        source = validated.reset_index(drop=True).copy()
        source["fact_position"] = source.index
        members = membership.merge(source, on="fact_position", how="left", validate="many_to_one")
        members = members.loc[members["month"].isin(months)].copy()
    metrics = _build_metrics(members)
    composition = _build_composition(members)
    coverage = _build_coverage(
        catalog, members, metrics, composition, months, normalized_data_version
    )
    return validate_class3_analysis_tables(
        Class3AnalysisTables(catalog, metrics, composition, coverage)
    )
