"""Versioned contracts shared by the Class 1 and Class 3 pipelines."""

from .product_key import MAX_EXACT_FLOAT_INTEGER, normalize_integer_code

from .supply_monthly import (
    BLOCK_DEDUPLICATION_UNVERIFIED,
    BLOCK_NEGATIVE_FORWARD_VALUE,
    BLOCK_PRODUCT_KEY_INVALID,
    BLOCK_TRANSACTION_SIGN_POLICY_PENDING,
    BLOCK_TRANSACTION_TYPE_UNKNOWN,
    FACT_SCHEMA_NAME,
    FACT_SCHEMA_VERSION,
    MONTHLY_FACT_COLUMNS,
    MONTHLY_FACT_SCHEMA,
    PRODUCT_KEY_COLUMNS,
    PRODUCT_KEY_FIELD_TYPES,
    SOURCE_REQUIRED_COLUMNS,
    ContractValidationError,
    assign_product_ids,
    build_product_id,
    empty_monthly_fact,
    normalize_source_rows,
    validate_monthly_fact,
)

__all__ = [
    "BLOCK_DEDUPLICATION_UNVERIFIED",
    "BLOCK_NEGATIVE_FORWARD_VALUE",
    "BLOCK_PRODUCT_KEY_INVALID",
    "BLOCK_TRANSACTION_SIGN_POLICY_PENDING",
    "BLOCK_TRANSACTION_TYPE_UNKNOWN",
    "FACT_SCHEMA_NAME",
    "FACT_SCHEMA_VERSION",
    "MONTHLY_FACT_COLUMNS",
    "MONTHLY_FACT_SCHEMA",
    "PRODUCT_KEY_COLUMNS",
    "PRODUCT_KEY_FIELD_TYPES",
    "SOURCE_REQUIRED_COLUMNS",
    "ContractValidationError",
    "MAX_EXACT_FLOAT_INTEGER",
    "assign_product_ids",
    "build_product_id",
    "empty_monthly_fact",
    "normalize_source_rows",
    "normalize_integer_code",
    "validate_monthly_fact",
]
