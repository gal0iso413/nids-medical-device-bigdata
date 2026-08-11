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


class ContractValidationError(ValueError):
    """Raised when source rows or a monthly fact violate the contract."""


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
        rows = series.index[invalid].tolist()
        prefix = f"{blocked_status}: " if blocked_status else ""
        raise ContractValidationError(
            f"{prefix}{column!r} is missing or blank at source rows: {rows}"
        )
    return normalized


def _normalize_optional_text_series(series: pd.Series) -> pd.Series:
    normalized = series.astype("string").str.strip()
    return normalized.mask(normalized.eq(""), pd.NA)


def _normalize_integer_code_series(series: pd.Series, *, column: str) -> pd.Series:
    """Normalize an official integer code without accepting fractional values."""
    if pd.api.types.is_float_dtype(series.dtype):
        finite = series.dropna()
        precision_risk = finite.abs().gt(2**53)
        if precision_risk.any():
            rows = finite.index[precision_risk].tolist()
            raise ContractValidationError(
                f"{BLOCK_PRODUCT_KEY_INVALID}: {column!r} contains float values "
                f"outside the exact integer range at source rows: {rows}"
            )

    text = series.astype("string").str.strip()
    missing = text.isna() | text.eq("")
    unsigned = text.str.removeprefix("+")
    valid = unsigned.str.match(r"^\d+(?:\.0+)?$", na=False)
    invalid = missing | ~valid
    if invalid.any():
        rows = series.index[invalid].tolist()
        raise ContractValidationError(
            f"{BLOCK_PRODUCT_KEY_INVALID}: {column!r} is null, blank, or not "
            f"an integer code at source rows: {rows}"
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
        rows = series.index[invalid].tolist()
        raise ContractValidationError(
            f"{column!r} contains non-decimal or non-finite values at source rows: {rows}"
        )

    distinct_tokens = pd.unique(text[~missing])
    token_to_decimal: dict[str, Decimal] = {}
    for token in distinct_tokens:
        try:
            decimal_value = Decimal(str(token))
        except (InvalidOperation, ValueError) as exc:
            raise ContractValidationError(
                f"{column!r} contains an invalid decimal token: {token!r}"
            ) from exc
        if not decimal_value.is_finite():
            raise ContractValidationError(
                f"{column!r} contains a non-finite decimal token: {token!r}"
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
        keys = [tuple(values) for values in conflicts.to_numpy().tolist()]
        raise ContractValidationError(
            "blocked:source_row_conflict: identical idempotency keys contain "
            f"different normalized content: {keys}"
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
        raise ContractValidationError(f"Missing source columns: {missing}")

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
    invalid_dates = normalized.index[parsed_dates.isna()].tolist()
    if invalid_dates:
        raise ContractValidationError(
            f"Invalid or missing supply_date at source rows: {invalid_dates}"
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
    invalid = [
        index
        for index, value in series.items()
        if not _is_missing(value) and not isinstance(value, Decimal)
    ]
    if invalid:
        raise ContractValidationError(
            f"{column!r} must contain Decimal or null; invalid rows: {invalid}"
        )


def validate_monthly_fact(fact: pd.DataFrame) -> pd.DataFrame:
    """Validate exact schema, grain uniqueness, and field invariants."""
    if not isinstance(fact, pd.DataFrame):
        raise ContractValidationError("Monthly fact must be a pandas DataFrame.")
    if tuple(fact.columns) != MONTHLY_FACT_COLUMNS:
        raise ContractValidationError(
            "Monthly fact columns do not match the versioned schema: "
            f"expected {list(MONTHLY_FACT_COLUMNS)}, got {list(fact.columns)}"
        )
    if fact.empty:
        return fact.copy(deep=True)

    wrong_string_dtypes = [
        column for column in _STRING_FACT_COLUMNS
        if str(fact[column].dtype) != "string"
    ]
    wrong_count_dtypes = [
        column for column in _COUNT_COLUMNS if str(fact[column].dtype) != "Int64"
    ]
    if wrong_string_dtypes or wrong_count_dtypes:
        raise ContractValidationError(
            "Monthly fact dtypes do not match the contract: "
            f"string={wrong_string_dtypes}, Int64={wrong_count_dtypes}"
        )

    invalid_months = []
    for index, value in fact["month"].items():
        text = str(value)
        if not _MONTH_PATTERN.match(text):
            invalid_months.append(index)
            continue
        try:
            pd.to_datetime(text, format="%Y%m")
        except ValueError:
            invalid_months.append(index)
    if invalid_months:
        raise ContractValidationError(f"Invalid YYYYMM values at rows: {invalid_months}")

    grain = ["month", "src_company_id", "dst_company_id", "product_id"]
    duplicate_rows = fact.index[fact.duplicated(grain, keep=False)].tolist()
    if duplicate_rows:
        raise ContractValidationError(f"Duplicate monthly fact grain at rows: {duplicate_rows}")

    for column in ("src_company_id", "dst_company_id", "product_id", "source_version"):
        missing_rows = fact.index[
            fact[column].isna() | fact[column].str.strip().eq("")
        ].tolist()
        if missing_rows:
            raise ContractValidationError(f"{column!r} is required at rows: {missing_rows}")
    invalid_products = fact.index[
        ~fact["product_id"].str.match(r"^p3:[0-9a-f]{64}$", na=False)
    ].tolist()
    if invalid_products:
        raise ContractValidationError(f"Invalid product_id at rows: {invalid_products}")

    for column in _COUNT_COLUMNS:
        numeric = pd.to_numeric(fact[column], errors="coerce")
        invalid = fact.index[
            numeric.isna() | (numeric < 0) | (numeric % 1 != 0)
        ].tolist()
        if invalid:
            raise ContractValidationError(
                f"Invalid non-negative integer {column!r}: {invalid}"
            )
    if fact["tx_count"].le(0).any():
        raise ContractValidationError("tx_count must be positive for every aggregate row.")
    for column in _COUNT_COLUMNS[1:]:
        if fact[column].gt(fact["tx_count"]).any():
            raise ContractValidationError(f"{column} cannot exceed tx_count.")

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
        ].tolist()
        if invalid_null:
            raise ContractValidationError(
                f"{column!r} nullability disagrees with its valid-row count: {invalid_null}"
            )
        negative = fact.index[
            fact[column].map(
                lambda value: False if _is_missing(value) else value < Decimal("0")
            )
        ].tolist()
        if negative:
            raise ContractValidationError(
                f"{column!r} cannot contain negative forward totals: {negative}"
            )

    if fact["quality_flags"].isna().any():
        raise ContractValidationError(
            "quality_flags must be an empty or semicolon-delimited string."
        )
    unordered_flags = []
    for index, value in fact["quality_flags"].items():
        flags = [flag for flag in str(value).split(";") if flag]
        if flags != sorted(set(flags)):
            unordered_flags.append(index)
    if unordered_flags:
        raise ContractValidationError(
            f"quality_flags must be unique and sorted at rows: {unordered_flags}"
        )
    return fact.copy(deep=True)
