"""Deterministic aggregate builders for offline pipelines."""

from .company_counterparty_product_month import (
    UnsupportedTransactionTypeError,
    aggregate_company_counterparty_product_month,
)

__all__ = [
    "UnsupportedTransactionTypeError",
    "aggregate_company_counterparty_product_month",
]
