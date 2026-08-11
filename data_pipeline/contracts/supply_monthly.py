"""Contract for the company-counterparty-product-month fact table.

The module accepts normalized, in-memory source rows only. It performs no
file, database, API, or package I/O and never derives ``piece_qty`` from raw
quantity or packaging fields.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any, Final

import numpy as np
import pandas as pd


FACT_SCHEMA_NAME: Final = "fact_company_counterparty_product_month"
FACT_SCHEMA_VERSION: Final = "1.0.0"

BLOCK_DEDUPLICATION_UNVERIFIED: Final = "blocked:deduplication_unverified"
BLOCK_PRODUCT_KEY_INVALID: Final = "blocked:product_key_invalid"
BLOCK_NEGATIVE_FORWARD_VALUE: Final = "blocked:negative_forward_value"
BLOCK_TRANSACTION_SIGN_POLICY_PENDING: Final = (
    "blocked:transaction_sign_policy_pending"
)
BLOCK_TRANSACTION_TYPE_UNKNOWN: Final = "blocked:transaction_type_unknown"

SOURCE_REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "supply_date",
    "src_company_id",
    "dst_company_id",
    "item_serial",
    "model_serial",
    "udi_serial",
    "item_group_id",
    "item_name_id",
    "transaction_type",
    "amount_clean",
    "raw_supply_qty",
    "piece_qty",
    "udi",
    "supplier_type",
    "receiver_type",
    "supplier_region",
    "receiver_region",
    "source_version",
    "source_row_id",
)

MONTHLY_FACT_SCHEMA: Final[dict[str, str]] = {
    "month": "string[YYYYMM]",
    "src_company_id": "string",
    "dst_company_id": "string",
    "product_id": "string[sha256-of-canonical-3-key]",
    "item_group_id": "string|null",
    "item_name_id": "string|null",
    "tx_count": "Int64",
    "amount_sum_clean": "Decimal|null",
    "amount_valid_row_count": "Int64",
    "raw_supply_qty_sum": "Decimal|null",
    "raw_supply_qty_valid_row_count": "Int64",
    "piece_qty_sum": "Decimal|null",
    "piece_qty_valid_row_count": "Int64",
    "unique_udi_count": "Int64",
    "active_day_count": "Int64",
    "supplier_type": "string|null",
    "receiver_type": "string|null",
    "supplier_region": "string|null",
    "receiver_region": "string|null",
    "source_version": "string",
    "quality_flags": "string[sorted-semicolon-delimited]",
}
MONTHLY_FACT_COLUMNS: Final[tuple[str, ...]] = tuple(MONTHLY_FACT_SCHEMA)

PRODUCT_KEY_COLUMNS: Final[tuple[str, str, str]] = (
    "item_serial",
    "model_serial",
    "udi_serial",
)
# The three official serial-number fields are integer code fields. Other code
# fields remain strings, so their leading zeroes are preserved.
PRODUCT_KEY_FIELD_TYPES: Final[dict[str, str]] = {
    "item_serial": "integer_code",
    "model_serial": "integer_code",
    "udi_serial": "integer_code",
}
_IDEMPOTENCY_COLUMNS: Final[tuple[str, str]] = (
    "source_version",
    "source_row_id",
)
_REQUIRED_TEXT_COLUMNS: Final[tuple[str, ...]] = (
    "src_company_id",
    "dst_company_id",
    "transaction_type",
    "source_version",
    "source_row_id",
)
_OPTIONAL_TEXT_COLUMNS: Final[tuple[str, ...]] = (
    "item_group_id",
    "item_name_id",
    "udi",
    "supplier_type",
    "receiver_type",
    "supplier_region",
    "receiver_region",
)
_DECIMAL_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "amount_clean",
    "raw_supply_qty",
    "piece_qty",
)
_DECIMAL_FACT_COLUMNS: Final[tuple[str, ...]] = (
    "amount_sum_clean",
    "raw_supply_qty_sum",
    "piece_qty_sum",
)
_COUNT_COLUMNS: Final[tuple[str, ...]] = (
    "tx_count",
    "amount_valid_row_count",
    "raw_supply_qty_valid_row_count",
    "piece_qty_valid_row_count",
    "unique_udi_count",
    "active_day_count",
)
_STRING_FACT_COLUMNS: Final[tuple[str, ...]] = (
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
_MONTH_PATTERN = re.compile(r"^\d{6}$")
_DECIMAL_PATTERN = r"^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?$"
_DIAGNOSTIC_SAMPLE_LIMIT: Final = 20
_DIAGNOSTIC_VALUE_LIMIT: Final = 80


class ContractValidationError(ValueError):
    """Raised when source rows or a monthly fact violate the contract."""


def _bounded_diagnostic(values: Any) -> str:
    """Return a bounded count/sample summary without materializing all values."""
    total = len(values)
    sample_values = values[:_DIAGNOSTIC_SAMPLE_LIMIT]
    if isinstance(sample_values, (pd.Index, pd.Series)):
        sample_values = sample_values.tolist()
    else:
        sample_values = list(sample_values)

    sample: list[str] = []
    for value in sample_values:
        text = str(value)
        if len(text) > _DIAGNOSTIC_VALUE_LIMIT:
            text = text[: _DIAGNOSTIC_VALUE_LIMIT - 3] + "..."
        sample.append(text)
    omitted = max(total - len(sample), 0)
    return f"total={total}; sample={sample}; omitted={omitted}"


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _normalize_required_text_series(
    series: pd.Series,
    *,
    column: str,
    blocked_status: str | None = None,
) -> pd.Series:
    normalized = series.astype("string").str.strip()
    invalid = normalized.isna() | normalized.eq("")
    if invalid.any():
        prefix = f"{blocked_status}: " if blocked_status else ""
        raise ContractValidationError(
            f"{prefix}{column!r} is missing or blank at source rows: "
            f"{_bounded_diagnostic(series.index[invalid])}"
        )
    return normalized


def _normalize_optional_text_series(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip()
    return normalized.mask(normalized.eq(""), pd.NA)


def _normalize_integer_code_series(series: pd.Series, *, column: str) -> pd.Series:
    """Normalize an official integer code without accepting fractional values."""
    actual_float = series.map(lambda value: isinstance(value, (float, np.floating)))
    float_values = series.loc[actual_float & series.notna()]
    if not float_values.empty:
        numeric_float = float_values.astype("float64")
        invalid_float = ~np.isfinite(numeric_float) | numeric_float.abs().gt(2**53)
        if invalid_float.any():
            raise ContractValidationError(
                f"{BLOCK_PRODUCT_KEY_INVALID}: {column!r} contains non-finite "
                "or precision-unsafe float values at source rows: "
                f"{_bounded_diagnostic(float_values.index[invalid_float])}"
            )

    text = series.astype("string").str.strip()
    missing = text.isna() | text.eq("")
    unsigned = text.str.removeprefix("+")
    valid = unsigned.str.match(r"^\d+(?:\.0+)?$", na=False)
    invalid = missing | ~valid
    if invalid.any():
        raise ContractValidationError(
            f"{BLOCK_PRODUCT_KEY_INVALID}: {column!r} is null, blank, or not "
            "an integer code at source rows: "
            f"{_bounded_diagnostic(series.index[invalid])}"
        )

    canonical = unsigned.str.replace(r"\.0+$", "", regex=True).str.lstrip("0")
    canonical = canonical.mask(canonical.eq(""), "0")
    return canonical.astype("string")


def _normalize_decimal_series(series: pd.Series, *, column: str) -> pd.Series:
    """Create exact Decimals by converting each distinct source token once."""
    text = series.astype("string").str.strip()
    missing = series.isna() | text.isna() | text.eq("")
    valid = text.str.match(_DECIMAL_PATTERN, na=False)
    invalid = ~missing & ~valid
    if invalid.any():
        raise ContractValidationError(
            f"{column!r} contains non-decimal or non-finite values at source rows: "
            f"{_bounded_diagnostic(series.index[invalid])}"
        )

    distinct_tokens = pd.unique(text[~missing])
    token_to_decimal: dict[str, Decimal] = {}
    for token in distinct_tokens:
        try:
            decimal_value = Decimal(str(token))
        except (InvalidOperation, ValueError) as exc:
            token_rows = series.index[text.eq(str(token))]
            raise ContractValidationError(
                f"{column!r} contains an invalid decimal token at source rows: "
                f"{_bounded_diagnostic(token_rows)}"
            ) from exc
        if not decimal_value.is_finite():
            token_rows = series.index[text.eq(str(token))]
            raise ContractValidationError(
                f"{column!r} contains a non-finite decimal token at source rows: "
                f"{_bounded_diagnostic(token_rows)}"
            )
        token_to_decimal[str(token)] = decimal_value

    normalized = text.map(token_to_decimal).astype("object")
    normalized.loc[missing] = pd.NA
    return normalized


def _canonical_product_payload(values: tuple[str, str, str]) -> str:
    # JSON string escaping and array boundaries make delimiter collisions
    # impossible while remaining language- and process-independent.
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def _hash_normalized_product_key(values: tuple[str, str, str]) -> str:
    payload = _canonical_product_payload(values)
    return f"p3:{sha256(payload.encode('utf-8')).hexdigest()}"


def build_product_id(item_serial: Any, model_serial: Any, udi_serial: Any) -> str:
    """Build a stable ID from the normalized official three-key tuple."""
    one_row = pd.DataFrame(
        {
            "item_serial": [item_serial],
            "model_serial": [model_serial],
            "udi_serial": [udi_serial],
        }
    )
    values = tuple(
        _normalize_integer_code_series(one_row[column], column=column).iat[0]
        for column in PRODUCT_KEY_COLUMNS
    )
    return _hash_normalized_product_key(values)


def assign_product_ids(rows: pd.DataFrame) -> pd.DataFrame:
    """Hash each distinct normalized three-key combination exactly once."""
    unique_keys = rows.loc[:, PRODUCT_KEY_COLUMNS].drop_duplicates(ignore_index=True)
    key_tuples = list(
        zip(*(unique_keys[column].array for column in PRODUCT_KEY_COLUMNS))
    )
    product_ids = [_hash_normalized_product_key(values) for values in key_tuples]
    lookup = pd.Series(
        product_ids,
        index=pd.MultiIndex.from_frame(unique_keys),
        dtype="string",
    )
    row_keys = pd.MultiIndex.from_frame(rows.loc[:, PRODUCT_KEY_COLUMNS])
    result = rows.copy(deep=True)
    result["product_id"] = lookup.reindex(row_keys).array
    return result


def _deduplicate_source_rows(rows: pd.DataFrame) -> pd.DataFrame:
    duplicate_key_mask = rows.duplicated(list(_IDEMPOTENCY_COLUMNS), keep=False)
    if not duplicate_key_mask.any():
        return rows

    duplicate_rows = rows.loc[duplicate_key_mask]
    try:
        distinct_variants = duplicate_rows.drop_duplicates(ignore_index=True)
    except TypeError as exc:
        raise ContractValidationError(
            "Source rows must contain scalar values for deterministic deduplication."
        ) from exc
    conflict_mask = distinct_variants.duplicated(
        list(_IDEMPOTENCY_COLUMNS), keep=False
    )
    if conflict_mask.any():
        conflicts = (
            distinct_variants.loc[conflict_mask, list(_IDEMPOTENCY_COLUMNS)]
            .drop_duplicates()
            .sort_values(list(_IDEMPOTENCY_COLUMNS), kind="stable")
        )
        raise ContractValidationError(
            "blocked:source_row_conflict: identical idempotency keys contain "
            "different normalized content; conflicting source_row_id values: "
            f"{_bounded_diagnostic(conflicts['source_row_id'])}"
        )
    return rows.drop_duplicates(list(_IDEMPOTENCY_COLUMNS), keep="first").copy()


def normalize_source_rows(rows: pd.DataFrame) -> pd.DataFrame:
    """Validate, normalize, and idempotently deduplicate source rows."""
    if not isinstance(rows, pd.DataFrame):
        raise ContractValidationError("Source rows must be a pandas DataFrame.")

    if "source_row_id" not in rows.columns:
        raise ContractValidationError(
            f"{BLOCK_DEDUPLICATION_UNVERIFIED}: missing required source_row_id"
        )
    missing = sorted(set(SOURCE_REQUIRED_COLUMNS) - set(rows.columns))
    if missing:
        raise ContractValidationError(
            f"Missing source columns: {_bounded_diagnostic(missing)}"
        )

    normalized = rows.copy(deep=True)
    for column in _REQUIRED_TEXT_COLUMNS:
        blocked_status = (
            BLOCK_DEDUPLICATION_UNVERIFIED if column == "source_row_id" else None
        )
        normalized[column] = _normalize_required_text_series(
            normalized[column], column=column, blocked_status=blocked_status
        )
    normalized["transaction_type"] = normalized["transaction_type"].str.upper()

    for column in PRODUCT_KEY_COLUMNS:
        normalized[column] = _normalize_integer_code_series(
            normalized[column], column=column
        )
    for column in _OPTIONAL_TEXT_COLUMNS:
        normalized[column] = _normalize_optional_text_series(normalized[column])
    for column in _DECIMAL_SOURCE_COLUMNS:
        normalized[column] = _normalize_decimal_series(
            normalized[column], column=column
        )

    parsed_dates = pd.to_datetime(normalized["supply_date"], errors="coerce")
    invalid_dates = normalized.index[parsed_dates.isna()]
    if len(invalid_dates):
        raise ContractValidationError(
            "Invalid or missing supply_date at source rows: "
            f"{_bounded_diagnostic(invalid_dates)}"
        )
    normalized["supply_date"] = parsed_dates.dt.normalize()

    if "row_quality_flags" not in normalized.columns:
        normalized["row_quality_flags"] = ""
    else:
        normalized["row_quality_flags"] = (
            normalized["row_quality_flags"]
            .astype("string")
            .fillna("")
            .str.strip()
        )
    return _deduplicate_source_rows(normalized)


def empty_monthly_fact() -> pd.DataFrame:
    """Return an empty DataFrame with contracted column order and dtypes."""
    frame = pd.DataFrame(columns=MONTHLY_FACT_COLUMNS)
    for column in _STRING_FACT_COLUMNS:
        frame[column] = frame[column].astype("string")
    for column in _COUNT_COLUMNS:
        frame[column] = frame[column].astype("Int64")
    return frame


def _require_decimal_or_null(series: pd.Series, column: str) -> None:
    invalid_mask = series.map(
        lambda value: not _is_missing(value) and not isinstance(value, Decimal)
    )
    invalid = series.index[invalid_mask]
    if len(invalid):
        raise ContractValidationError(
            f"{column!r} must contain Decimal or null; invalid rows: "
            f"{_bounded_diagnostic(invalid)}"
        )


def validate_monthly_fact(fact: pd.DataFrame) -> pd.DataFrame:
    """Validate exact schema, grain uniqueness, and field invariants."""
    if not isinstance(fact, pd.DataFrame):
        raise ContractValidationError("Monthly fact must be a pandas DataFrame.")
    if tuple(fact.columns) != MONTHLY_FACT_COLUMNS:
        raise ContractValidationError(
            "Monthly fact columns do not match the versioned schema: "
            f"expected {_bounded_diagnostic(MONTHLY_FACT_COLUMNS)}, "
            f"got {_bounded_diagnostic(fact.columns)}"
        )

    wrong_string_dtypes = [
        column for column in _STRING_FACT_COLUMNS
        if str(fact[column].dtype) != "string"
    ]
    wrong_count_dtypes = [
        column for column in _COUNT_COLUMNS if str(fact[column].dtype) != "Int64"
    ]
    wrong_decimal_dtypes = [
        column for column in _DECIMAL_FACT_COLUMNS
        if not pd.api.types.is_object_dtype(fact[column].dtype)
    ]
    wrong_dtypes = wrong_string_dtypes + wrong_count_dtypes + wrong_decimal_dtypes
    if wrong_dtypes:
        raise ContractValidationError(
            "Monthly fact dtypes do not match the contract; invalid columns: "
            f"{_bounded_diagnostic(wrong_dtypes)}"
        )
    if fact.empty:
        return fact.copy(deep=True)

    month_text = fact["month"].astype("string")
    invalid_month_mask = (
        ~month_text.str.match(_MONTH_PATTERN, na=False)
        | pd.to_datetime(month_text, format="%Y%m", errors="coerce").isna()
    )
    invalid_months = fact.index[invalid_month_mask]
    if len(invalid_months):
        raise ContractValidationError(
            f"Invalid YYYYMM values at rows: {_bounded_diagnostic(invalid_months)}"
        )

    grain = ["month", "src_company_id", "dst_company_id", "product_id"]
    duplicate_rows = fact.index[fact.duplicated(grain, keep=False)]
    if len(duplicate_rows):
        raise ContractValidationError(
            "Duplicate monthly fact grain at rows: "
            f"{_bounded_diagnostic(duplicate_rows)}"
        )

    for column in ("src_company_id", "dst_company_id", "product_id", "source_version"):
        missing_rows = fact.index[
            fact[column].isna() | fact[column].str.strip().eq("")
        ]
        if len(missing_rows):
            raise ContractValidationError(
                f"{column!r} is required at rows: "
                f"{_bounded_diagnostic(missing_rows)}"
            )
    invalid_products = fact.index[
        ~fact["product_id"].str.match(r"^p3:[0-9a-f]{64}$", na=False)
    ]
    if len(invalid_products):
        raise ContractValidationError(
            f"Invalid product_id at rows: {_bounded_diagnostic(invalid_products)}"
        )

    for column in _COUNT_COLUMNS:
        numeric = pd.to_numeric(fact[column], errors="coerce")
        invalid = fact.index[
            numeric.isna() | (numeric < 0) | (numeric % 1 != 0)
        ]
        if len(invalid):
            raise ContractValidationError(
                f"Invalid non-negative integer {column!r} at rows: "
                f"{_bounded_diagnostic(invalid)}"
            )
    nonpositive_tx = fact.index[fact["tx_count"].le(0)]
    if len(nonpositive_tx):
        raise ContractValidationError(
            "tx_count must be positive at rows: "
            f"{_bounded_diagnostic(nonpositive_tx)}"
        )
    for column in _COUNT_COLUMNS[1:]:
        excessive = fact.index[fact[column].gt(fact["tx_count"])]
        if len(excessive):
            raise ContractValidationError(
                f"{column} cannot exceed tx_count at rows: "
                f"{_bounded_diagnostic(excessive)}"
            )

    count_for_sum = {
        "amount_sum_clean": "amount_valid_row_count",
        "raw_supply_qty_sum": "raw_supply_qty_valid_row_count",
        "piece_qty_sum": "piece_qty_valid_row_count",
    }
    for column in _DECIMAL_FACT_COLUMNS:
        _require_decimal_or_null(fact[column], column)
        valid_count = fact[count_for_sum[column]]
        invalid_null = fact.index[
            (valid_count.eq(0) & fact[column].notna())
            | (valid_count.gt(0) & fact[column].isna())
        ]
        if len(invalid_null):
            raise ContractValidationError(
                f"{column!r} nullability disagrees with its valid-row count at rows: "
                f"{_bounded_diagnostic(invalid_null)}"
            )
        negative = fact.index[
            fact[column].map(
                lambda value: False if _is_missing(value) else value < Decimal("0")
            )
        ]
        if len(negative):
            raise ContractValidationError(
                f"{column!r} cannot contain negative forward totals at rows: "
                f"{_bounded_diagnostic(negative)}"
            )

    missing_quality_flags = fact.index[fact["quality_flags"].isna()]
    if len(missing_quality_flags):
        raise ContractValidationError(
            "quality_flags must be an empty or semicolon-delimited string at rows: "
            f"{_bounded_diagnostic(missing_quality_flags)}"
        )
    def _quality_flags_are_ordered(value: Any) -> bool:
        flags = [flag for flag in str(value).split(";") if flag]
        return flags == sorted(set(flags))

    unordered_flags = fact.index[
        ~fact["quality_flags"].map(_quality_flags_are_ordered)
    ]
    if len(unordered_flags):
        raise ContractValidationError(
            "quality_flags must be unique and sorted at rows: "
            f"{_bounded_diagnostic(unordered_flags)}"
        )
    return fact.copy(deep=True)
