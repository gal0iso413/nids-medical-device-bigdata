"""Pure builder for the shared company-counterparty-product-month fact."""

from __future__ import annotations

from decimal import Decimal
from typing import Final

import pandas as pd

from data_pipeline.contracts.supply_monthly import (
    BLOCK_NEGATIVE_FORWARD_VALUE,
    BLOCK_TRANSACTION_SIGN_POLICY_PENDING,
    BLOCK_TRANSACTION_TYPE_UNKNOWN,
    MONTHLY_FACT_COLUMNS,
    ContractValidationError,
    _bounded_diagnostic,
    _bounded_mask_diagnostic,
    assign_product_ids,
    empty_monthly_fact,
    normalize_source_rows,
    validate_monthly_fact,
)


FORWARD_TRANSACTION_TYPE: Final = "SUPPLY"
PENDING_SIGN_TRANSACTION_TYPES: Final[frozenset[str]] = frozenset(
    {"RETURN", "RECALL"}
)


class UnsupportedTransactionTypeError(ContractValidationError):
    """Raised when a transaction type cannot enter the forward-supply fact."""


def _raise_for_transaction_types(transaction_types: pd.Series) -> None:
    values = set(transaction_types.dropna().astype("string"))
    pending = sorted(values & PENDING_SIGN_TRANSACTION_TYPES)
    if pending:
        raise UnsupportedTransactionTypeError(
            f"{BLOCK_TRANSACTION_SIGN_POLICY_PENDING}: return/recall rows cannot "
            "be aggregated before sign-policy approval; found: "
            f"{_bounded_diagnostic(pending)}"
        )
    unknown = sorted(values - {FORWARD_TRANSACTION_TYPE})
    if unknown:
        raise UnsupportedTransactionTypeError(
            f"{BLOCK_TRANSACTION_TYPE_UNKNOWN}: unknown transaction types cannot "
            f"be treated as forward supply; found: {_bounded_diagnostic(unknown)}"
        )


def _raise_for_negative_forward_values(rows: pd.DataFrame) -> None:
    for column in ("amount_clean", "raw_supply_qty", "piece_qty"):
        negative = rows[column].map(
            lambda value: False if pd.isna(value) else value < Decimal("0")
        )
        if negative.any():
            negative_diagnostic = _bounded_mask_diagnostic(
                negative,
                sample_frame=rows,
                sample_column="source_row_id",
            )
            raise ContractValidationError(
                f"{BLOCK_NEGATIVE_FORWARD_VALUE}: {column!r} is negative for "
                "source_row_id values: "
                f"{negative_diagnostic}"
            )


def _merge_source_quality_flags(series: pd.Series) -> str:
    flags: set[str] = set()
    for value in series.dropna().astype(str):
        for flag in value.replace("|", ";").split(";"):
            normalized = flag.strip()
            if normalized:
                flags.add(normalized)
    return ";".join(sorted(flags))


def _quality_flag_series(
    *,
    source_flags: pd.Series,
    flag_conditions: dict[str, pd.Series],
) -> pd.Series:
    ordered_names = sorted(flag_conditions)
    condition_arrays = [flag_conditions[name].to_numpy(dtype=bool) for name in ordered_names]
    generated_by_row = zip(*condition_arrays) if condition_arrays else [()] * len(source_flags)
    result = []
    for source_value, generated in zip(source_flags.astype(str), generated_by_row):
        flags = {flag for flag in source_value.split(";") if flag}
        flags.update(
            name for name, enabled in zip(ordered_names, generated) if enabled
        )
        result.append(";".join(sorted(flags)))
    return pd.Series(result, index=source_flags.index, dtype="string")


def aggregate_company_counterparty_product_month(rows: pd.DataFrame) -> pd.DataFrame:
    """Build a deterministic fact from validated forward-supply source rows.

    Exact duplicate idempotency keys are removed during normalization. Product
    IDs are hashed once per distinct normalized three-key tuple. Decimal inputs
    remain exact objects and are aggregated by pandas groupby; ``piece_qty`` is
    accepted only when already validated upstream and is never derived here.
    """
    normalized = normalize_source_rows(rows)
    if normalized.empty:
        return empty_monthly_fact()

    source_versions = sorted(set(normalized["source_version"]))
    if len(source_versions) != 1:
        raise ContractValidationError(
            "One aggregation call must contain exactly one source_version; "
            f"found {len(source_versions)} versions"
        )
    source_version = source_versions[0]

    _raise_for_transaction_types(normalized["transaction_type"])
    _raise_for_negative_forward_values(normalized)

    normalized = assign_product_ids(normalized)
    normalized["month"] = normalized["supply_date"].dt.strftime("%Y%m")

    grain = ["month", "src_company_id", "dst_company_id", "product_id"]
    grouped = normalized.groupby(grain, sort=True, dropna=False, observed=True)
    fact = grouped.size().rename("tx_count").to_frame()

    decimal_fields = {
        "amount_clean": ("amount_sum_clean", "amount_valid_row_count"),
        "raw_supply_qty": (
            "raw_supply_qty_sum",
            "raw_supply_qty_valid_row_count",
        ),
        "piece_qty": ("piece_qty_sum", "piece_qty_valid_row_count"),
    }
    flag_conditions: dict[str, pd.Series] = {}
    for source_column, (sum_column, count_column) in decimal_fields.items():
        valid_count = grouped[source_column].count()
        fact[count_column] = valid_count
        fact[sum_column] = grouped[source_column].sum(min_count=1)
        flag_conditions[f"{source_column}_unavailable"] = valid_count.eq(0)
        flag_conditions[f"{source_column}_partial"] = (
            valid_count.gt(0) & valid_count.lt(fact["tx_count"])
        )

    optional_dimensions = (
        "item_group_id",
        "item_name_id",
        "supplier_type",
        "receiver_type",
        "supplier_region",
        "receiver_region",
    )
    for column in optional_dimensions:
        valid_count = grouped[column].count()
        distinct_count = grouped[column].nunique(dropna=True)
        value = grouped[column].first().mask(distinct_count.ne(1), pd.NA)
        fact[column] = value
        flag_conditions[f"{column}_missing"] = valid_count.lt(fact["tx_count"])
        flag_conditions[f"{column}_conflict"] = distinct_count.gt(1)

    udi_valid_count = grouped["udi"].count()
    fact["unique_udi_count"] = grouped["udi"].nunique(dropna=True)
    fact["active_day_count"] = grouped["supply_date"].nunique(dropna=True)
    flag_conditions["udi_unavailable"] = udi_valid_count.eq(0)
    flag_conditions["udi_partial"] = (
        udi_valid_count.gt(0) & udi_valid_count.lt(fact["tx_count"])
    )

    source_flags = grouped["row_quality_flags"].agg(_merge_source_quality_flags)
    fact["quality_flags"] = _quality_flag_series(
        source_flags=source_flags,
        flag_conditions=flag_conditions,
    )
    fact["source_version"] = source_version

    fact = fact.reset_index()
    fact = fact.loc[:, MONTHLY_FACT_COLUMNS]
    string_columns = (
        "month",
        "src_company_id",
        "dst_company_id",
        "product_id",
        "item_group_id",
        "item_name_id",
        "supplier_type",
        "receiver_type",
        "supplier_region",
        "receiver_region",
        "source_version",
        "quality_flags",
    )
    count_columns = (
        "tx_count",
        "amount_valid_row_count",
        "raw_supply_qty_valid_row_count",
        "piece_qty_valid_row_count",
        "unique_udi_count",
        "active_day_count",
    )
    for column in string_columns:
        fact[column] = fact[column].astype("string")
    for column in count_columns:
        fact[column] = fact[column].astype("Int64")
    fact = fact.sort_values(grain, kind="stable").reset_index(drop=True)
    return validate_monthly_fact(fact)
