"""Contract tests for the shared monthly supply fact."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import re
import unittest

import numpy as np
import pandas as pd

from data_pipeline.aggregates.company_counterparty_product_month import (
    UnsupportedTransactionTypeError,
    aggregate_company_counterparty_product_month,
)
from data_pipeline.contracts.supply_monthly import (
    FACT_SCHEMA_NAME,
    FACT_SCHEMA_VERSION,
    MONTHLY_FACT_COLUMNS,
    MONTHLY_FACT_SCHEMA,
    ContractValidationError,
    build_product_id,
    empty_monthly_fact,
    normalize_source_rows,
    validate_monthly_fact,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "supply_monthly_small.txt"


class SupplyMonthlyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = pd.DataFrame(json.loads(FIXTURE.read_text(encoding="utf-8")))

    def one_row(self, position: int = 0) -> pd.DataFrame:
        return self.source.iloc[[position]].copy().reset_index(drop=True)

    def test_schema_snapshot_is_versioned_exact_and_excludes_source_row_id(self) -> None:
        self.assertEqual(FACT_SCHEMA_NAME, "fact_company_counterparty_product_month")
        self.assertEqual(FACT_SCHEMA_VERSION, "1.0.0")
        self.assertEqual(tuple(MONTHLY_FACT_SCHEMA), MONTHLY_FACT_COLUMNS)
        self.assertEqual(
            MONTHLY_FACT_COLUMNS,
            (
                "month",
                "src_company_id",
                "dst_company_id",
                "product_id",
                "item_group_id",
                "item_name_id",
                "tx_count",
                "amount_sum_clean",
                "amount_valid_row_count",
                "raw_supply_qty_sum",
                "raw_supply_qty_valid_row_count",
                "piece_qty_sum",
                "piece_qty_valid_row_count",
                "unique_udi_count",
                "active_day_count",
                "supplier_type",
                "receiver_type",
                "supplier_region",
                "receiver_region",
                "source_version",
                "quality_flags",
            ),
        )
        fact = aggregate_company_counterparty_product_month(self.source)
        expected_dtypes = {
            **{
                column: "string"
                for column in (
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
            },
            **{
                column: "Int64"
                for column in (
                    "tx_count",
                    "amount_valid_row_count",
                    "raw_supply_qty_valid_row_count",
                    "piece_qty_valid_row_count",
                    "unique_udi_count",
                    "active_day_count",
                )
            },
            "amount_sum_clean": "object",
            "raw_supply_qty_sum": "object",
            "piece_qty_sum": "object",
        }
        self.assertEqual(
            {column: str(fact[column].dtype) for column in fact.columns},
            expected_dtypes,
        )
        self.assertNotIn("source_row_id", fact.columns)

    def test_empty_monthly_fact_passes_full_dtype_validation(self) -> None:
        empty = empty_monthly_fact()
        actual = validate_monthly_fact(empty)
        pd.testing.assert_frame_equal(actual, empty)

    def test_empty_fact_with_all_object_dtypes_is_rejected(self) -> None:
        invalid = pd.DataFrame(columns=MONTHLY_FACT_COLUMNS)
        self.assertTrue(all(str(dtype) == "object" for dtype in invalid.dtypes))
        with self.assertRaisesRegex(ContractValidationError, "dtypes"):
            validate_monthly_fact(invalid)

    def test_empty_fact_with_float_decimal_dtype_is_rejected(self) -> None:
        invalid = empty_monthly_fact()
        invalid["amount_sum_clean"] = pd.Series(dtype="float64")
        with self.assertRaisesRegex(
            ContractValidationError, "amount_sum_clean"
        ):
            validate_monthly_fact(invalid)

    def test_product_id_normalizes_whitespace_and_official_numeric_dtypes(self) -> None:
        product_ids = {
            build_product_id(" 10 ", "20", "30"),
            build_product_id(10, 20, 30),
            build_product_id(10.0, 20.0, 30.0),
            build_product_id("0010.0", "020.00", "+030"),
        }
        self.assertEqual(len(product_ids), 1)
        self.assertEqual(
            product_ids.pop(),
            "p3:5abac8d678c93550a6befe9461f5b36550deb212002577ae32b0e87770f94684",
        )
        self.assertEqual(
            build_product_id(Decimal("9007199254740993"), 20, 30),
            build_product_id("9007199254740993", 20, 30),
        )

    def test_object_dtype_safe_float_is_normalized(self) -> None:
        source = self.one_row()
        source["item_serial"] = source["item_serial"].astype(object)
        source.at[0, "item_serial"] = 10.0
        normalized = normalize_source_rows(source)
        self.assertEqual(normalized.loc[0, "item_serial"], "10")

    def test_object_dtype_precision_unsafe_float_is_blocked(self) -> None:
        for value in (float(2**53 + 2), np.float64(2**53 + 2)):
            with self.subTest(value_type=type(value).__name__):
                source = self.one_row()
                source["item_serial"] = source["item_serial"].astype(object)
                source.at[0, "item_serial"] = value
                with self.assertRaisesRegex(
                    ContractValidationError, "blocked:product_key_invalid"
                ):
                    normalize_source_rows(source)

    def test_nonfinite_float_product_keys_are_blocked(self) -> None:
        for value in (
            float("inf"),
            float("-inf"),
            np.float64("inf"),
            np.float64("-inf"),
        ):
            with self.subTest(value=value):
                source = self.one_row()
                source["item_serial"] = source["item_serial"].astype(object)
                source.at[0, "item_serial"] = value
                with self.assertRaisesRegex(
                    ContractValidationError, "blocked:product_key_invalid"
                ):
                    normalize_source_rows(source)

    def test_general_string_codes_preserve_leading_zeroes(self) -> None:
        source = self.one_row()
        source.loc[0, "item_group_id"] = " 0010 "
        source.loc[0, "item_name_id"] = " 000A "
        source.loc[0, "supplier_region"] = " 01 "
        fact = aggregate_company_counterparty_product_month(source)
        self.assertEqual(fact.loc[0, "item_group_id"], "0010")
        self.assertEqual(fact.loc[0, "item_name_id"], "000A")
        self.assertEqual(fact.loc[0, "supplier_region"], "01")

    def test_invalid_or_incomplete_three_key_is_blocked(self) -> None:
        for column, value in (
            ("item_serial", None),
            ("model_serial", "  "),
            ("udi_serial", "30.5"),
            ("item_serial", "not-a-code"),
        ):
            with self.subTest(column=column, value=value):
                source = self.one_row()
                source.loc[0, column] = value
                with self.assertRaisesRegex(
                    ContractValidationError, "blocked:product_key_invalid"
                ):
                    aggregate_company_counterparty_product_month(source)

    def test_exact_duplicate_source_row_is_aggregated_once(self) -> None:
        source = pd.concat([self.one_row(), self.one_row()], ignore_index=True)
        fact = aggregate_company_counterparty_product_month(source)
        self.assertEqual(fact.loc[0, "tx_count"], 1)
        self.assertEqual(fact.loc[0, "amount_sum_clean"], Decimal("1000"))

    def test_conflicting_content_for_same_source_row_id_is_blocked(self) -> None:
        first = self.one_row()
        conflicting = self.one_row()
        conflicting.loc[0, "amount_clean"] = "1001"
        source = pd.concat([first, conflicting], ignore_index=True)
        with self.assertRaisesRegex(
            ContractValidationError, "blocked:source_row_conflict"
        ):
            aggregate_company_counterparty_product_month(source)

    def test_missing_or_unverifiable_source_row_id_is_blocked(self) -> None:
        with self.assertRaisesRegex(
            ContractValidationError, "blocked:deduplication_unverified"
        ):
            aggregate_company_counterparty_product_month(
                self.one_row().drop(columns=["source_row_id"])
            )
        for value in (None, "  "):
            with self.subTest(value=value):
                source = self.one_row()
                source.loc[0, "source_row_id"] = value
                with self.assertRaisesRegex(
                    ContractValidationError, "blocked:deduplication_unverified"
                ):
                    aggregate_company_counterparty_product_month(source)

    def test_diagnostics_are_bounded_to_twenty_samples(self) -> None:
        def required_text_error(row_count: int) -> str:
            source = pd.concat(
                [self.one_row()] * row_count,
                ignore_index=True,
            )
            source["source_row_id"] = [
                f"bounded-{position}" for position in range(row_count)
            ]
            source["src_company_id"] = pd.NA
            with self.assertRaises(ContractValidationError) as context:
                aggregate_company_counterparty_product_month(source)
            return str(context.exception)

        message_25 = required_text_error(25)
        self.assertIn("total=25", message_25)
        self.assertIn("omitted=5", message_25)
        sample_match = re.search(r"sample=\[(.*?)\]; omitted=5", message_25)
        self.assertIsNotNone(sample_match)
        self.assertEqual(len(sample_match.group(1).split(", ")), 20)

        message_2500 = required_text_error(2500)
        self.assertIn("total=2500", message_2500)
        self.assertIn("omitted=2480", message_2500)
        self.assertLess(abs(len(message_2500) - len(message_25)), 20)

    def test_hundred_thousand_negative_rows_sample_only_twenty_source_ids(self) -> None:
        row_count = 100_000
        source = self.one_row().iloc[
            np.zeros(row_count, dtype=np.int64)
        ].reset_index(drop=True)
        source["source_row_id"] = (
            "negative-"
            + pd.Series(np.arange(row_count), dtype="int64").astype("string").str.zfill(6)
        )
        source["amount_clean"] = "-1"

        with self.assertRaisesRegex(
            ContractValidationError, "blocked:negative_forward_value"
        ) as context:
            aggregate_company_counterparty_product_month(source)

        message = str(context.exception)
        self.assertIn("total=100000", message)
        self.assertIn("omitted=99980", message)
        sample_match = re.search(r"sample=\[(.*?)\]; omitted=99980", message)
        self.assertIsNotNone(sample_match)
        samples = sample_match.group(1).split(", ")
        self.assertEqual(len(samples), 20)
        self.assertIn("negative-000019", samples[-1])
        self.assertNotIn("negative-000020", sample_match.group(1))

    def test_aggregate_preserves_grain_units_and_separate_valid_counts(self) -> None:
        original = self.source.copy(deep=True)
        fact = aggregate_company_counterparty_product_month(self.source)
        pd.testing.assert_frame_equal(self.source, original)
        self.assertEqual(len(fact), 4)

        row = fact[
            (fact["month"] == "202601")
            & (fact["src_company_id"] == "co:100")
            & (fact["dst_company_id"] == "co:200")
            & (fact["product_id"] == build_product_id("10", "20", "30"))
        ].iloc[0]
        self.assertEqual(row["tx_count"], 2)
        self.assertEqual(row["amount_sum_clean"], Decimal("1000"))
        self.assertEqual(row["amount_valid_row_count"], 1)
        self.assertEqual(row["raw_supply_qty_sum"], Decimal("5"))
        self.assertEqual(row["raw_supply_qty_valid_row_count"], 2)
        self.assertTrue(pd.isna(row["piece_qty_sum"]))
        self.assertEqual(row["piece_qty_valid_row_count"], 0)
        self.assertEqual(row["unique_udi_count"], 2)
        self.assertEqual(row["active_day_count"], 2)
        self.assertEqual(
            row["quality_flags"].split(";"),
            [
                "amount_clean_partial",
                "piece_qty_unavailable",
                "source_amount_missing",
            ],
        )

    def test_no_valid_piece_quantity_produces_null_sum_and_zero_count(self) -> None:
        source = self.source.copy()
        source["piece_qty"] = None
        source["packaging_inner_qty"] = "999"
        fact = aggregate_company_counterparty_product_month(source)
        self.assertTrue(fact["piece_qty_sum"].isna().all())
        self.assertTrue(fact["piece_qty_valid_row_count"].eq(0).all())

    def test_prevalidated_piece_quantity_is_aggregated_but_not_derived(self) -> None:
        fact = aggregate_company_counterparty_product_month(self.source)
        row = fact[
            fact["product_id"] == build_product_id("10", "20", "31")
        ].iloc[0]
        self.assertEqual(row["raw_supply_qty_sum"], Decimal("1"))
        self.assertEqual(row["raw_supply_qty_valid_row_count"], 1)
        self.assertEqual(row["piece_qty_sum"], Decimal("12"))
        self.assertEqual(row["piece_qty_valid_row_count"], 1)

    def test_decimal_sums_remain_exact_without_float_conversion(self) -> None:
        source = pd.concat([self.one_row(), self.one_row()], ignore_index=True)
        source.loc[0, "source_row_id"] = "decimal-1"
        source.loc[1, "source_row_id"] = "decimal-2"
        source.loc[0, "amount_clean"] = "0.1"
        source.loc[1, "amount_clean"] = "0.2"
        fact = aggregate_company_counterparty_product_month(source)
        self.assertEqual(fact.loc[0, "amount_sum_clean"], Decimal("0.3"))

    def test_negative_forward_amount_is_blocked(self) -> None:
        source = self.one_row()
        source.loc[0, "amount_clean"] = "-0.01"
        with self.assertRaisesRegex(
            ContractValidationError, "blocked:negative_forward_value"
        ):
            aggregate_company_counterparty_product_month(source)

    def test_negative_forward_raw_or_piece_quantity_is_blocked(self) -> None:
        for column in ("raw_supply_qty", "piece_qty"):
            with self.subTest(column=column):
                source = self.one_row()
                source.loc[0, column] = "-1"
                with self.assertRaisesRegex(
                    ContractValidationError, "blocked:negative_forward_value"
                ):
                    aggregate_company_counterparty_product_month(source)

    def test_zero_values_are_valid_and_distinct_from_null(self) -> None:
        source = self.one_row()
        source.loc[0, "amount_clean"] = "0"
        source.loc[0, "raw_supply_qty"] = "0"
        source.loc[0, "piece_qty"] = None
        fact = aggregate_company_counterparty_product_month(source)
        self.assertEqual(fact.loc[0, "amount_sum_clean"], Decimal("0"))
        self.assertEqual(fact.loc[0, "amount_valid_row_count"], 1)
        self.assertEqual(fact.loc[0, "raw_supply_qty_sum"], Decimal("0"))
        self.assertEqual(fact.loc[0, "raw_supply_qty_valid_row_count"], 1)
        self.assertTrue(pd.isna(fact.loc[0, "piece_qty_sum"]))
        self.assertEqual(fact.loc[0, "piece_qty_valid_row_count"], 0)

    def test_return_and_recall_are_blocked_until_sign_policy_is_approved(self) -> None:
        for transaction_type in ("RETURN", "RECALL"):
            with self.subTest(transaction_type=transaction_type):
                source = self.one_row()
                source.loc[0, "transaction_type"] = transaction_type
                with self.assertRaisesRegex(
                    UnsupportedTransactionTypeError,
                    "blocked:transaction_sign_policy_pending",
                ):
                    aggregate_company_counterparty_product_month(source)

    def test_unknown_transaction_type_is_blocked(self) -> None:
        source = self.one_row()
        source.loc[0, "transaction_type"] = "UNKNOWN_FLOW"
        with self.assertRaisesRegex(
            UnsupportedTransactionTypeError, "blocked:transaction_type_unknown"
        ):
            aggregate_company_counterparty_product_month(source)

    def test_aggregation_is_deterministic_under_row_reordering(self) -> None:
        expected = aggregate_company_counterparty_product_month(self.source)
        shuffled = self.source.sample(frac=1, random_state=17).reset_index(drop=True)
        actual = aggregate_company_counterparty_product_month(shuffled)
        pd.testing.assert_frame_equal(actual, expected)
        for flags in actual["quality_flags"]:
            parts = [part for part in flags.split(";") if part]
            self.assertEqual(parts, sorted(set(parts)))

    def test_mixed_source_versions_are_blocked(self) -> None:
        source = self.source.iloc[:2].copy()
        source.loc[source.index[1], "source_version"] = "fixture-v2"
        with self.assertRaisesRegex(
            ContractValidationError, "exactly one source_version"
        ):
            aggregate_company_counterparty_product_month(source)

    def test_three_key_product_id_does_not_collapse_on_equal_udi(self) -> None:
        fact = aggregate_company_counterparty_product_month(self.source)
        january_pair = fact[
            (fact["month"] == "202601")
            & (fact["src_company_id"] == "co:100")
            & (fact["dst_company_id"] == "co:200")
        ]
        self.assertEqual(len(january_pair), 2)
        self.assertEqual(january_pair["product_id"].nunique(), 2)
        self.assertIn(build_product_id("10", "20", "30"), set(january_pair["product_id"]))
        self.assertIn(build_product_id("10", "20", "31"), set(january_pair["product_id"]))

    def test_item_name_never_substitutes_for_missing_item_group(self) -> None:
        fact = aggregate_company_counterparty_product_month(self.source)
        row = fact[
            (fact["month"] == "202601") & (fact["dst_company_id"] == "co:201")
        ].iloc[0]
        self.assertTrue(pd.isna(row["item_group_id"]))
        self.assertEqual(row["item_name_id"], "ITEM-C")
        self.assertIn("item_group_id_missing", row["quality_flags"].split(";"))

    def test_missing_required_non_id_column_fails_closed(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "Missing source columns"):
            aggregate_company_counterparty_product_month(
                self.source.drop(columns=["udi_serial"])
            )

    def test_fact_validator_rejects_duplicate_grain(self) -> None:
        fact = aggregate_company_counterparty_product_month(self.source)
        duplicate = pd.concat([fact, fact.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ContractValidationError, "Duplicate monthly fact grain"):
            validate_monthly_fact(duplicate)

    def test_normalization_deduplicates_before_tx_count(self) -> None:
        source = pd.concat([self.one_row(), self.one_row()], ignore_index=True)
        normalized = normalize_source_rows(source)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized.loc[0, "source_row_id"], "row-001")


if __name__ == "__main__":
    unittest.main()
