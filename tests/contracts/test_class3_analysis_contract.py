"""Focused contract tests for the Class 3 local analysis data product."""

from __future__ import annotations

from decimal import Decimal
import unittest

import pandas as pd

from data_pipeline.aggregates.class3_analysis import build_class3_analysis
from data_pipeline.contracts.class3_analysis import (
    CLASS3_ANALYSIS_SCHEMA_VERSION,
    SELECTION_CATALOG_COLUMNS,
    SELECTION_COVERAGE_SUMMARY_COLUMNS,
    SELECTION_MONTH_COMPOSITION_COLUMNS,
    SELECTION_MONTH_METRIC_COLUMNS,
    empty_selection_catalog,
    empty_selection_coverage_summary,
    empty_selection_month_composition,
    empty_selection_month_metrics,
    serialize_class3_analysis,
)
from data_pipeline.contracts.supply_monthly import empty_monthly_fact


def make_fact(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults: dict[str, object] = {
        "month": "202401",
        "src_company_id": "supplier-1",
        "dst_company_id": "receiver-1",
        "product_id": "p3:" + "0" * 64,
        "item_group_id": "Group A",
        "item_name_id": "Item A",
        "tx_count": 1,
        "amount_sum_clean": Decimal("1.00"),
        "amount_valid_row_count": 1,
        "raw_supply_qty_sum": Decimal("2.00"),
        "raw_supply_qty_valid_row_count": 1,
        "piece_qty_sum": Decimal("20.00"),
        "piece_qty_valid_row_count": 1,
        "unique_udi_count": 1,
        "active_day_count": 1,
        "supplier_type": "manufacturer",
        "receiver_type": "distributor",
        "supplier_region": "11",
        "receiver_region": "26",
        "source_version": "source-v1",
        "quality_flags": "",
    }
    records = [{**defaults, **row} for row in rows]
    fact = empty_monthly_fact()
    fact = pd.concat([fact, pd.DataFrame(records)], ignore_index=True)
    for column in (
        "month", "src_company_id", "dst_company_id", "product_id", "item_group_id",
        "item_name_id", "supplier_type", "receiver_type", "supplier_region",
        "receiver_region", "source_version", "quality_flags",
    ):
        fact[column] = fact[column].astype("string")
    for column in (
        "tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count",
        "piece_qty_valid_row_count", "unique_udi_count", "active_day_count",
    ):
        fact[column] = fact[column].astype("Int64")
    return fact


class Class3AnalysisContractTests(unittest.TestCase):
    def build(self, rows: list[dict[str, object]], start: str = "202401", end: str = "202401"):
        return build_class3_analysis(
            make_fact(rows), period_start=start, period_end=end, data_version="complete-fingerprint"
        )

    def test_empty_output_schemas_have_exact_columns_and_dtypes(self) -> None:
        tables = self.build([])
        self.assertEqual(tuple(empty_selection_catalog()), SELECTION_CATALOG_COLUMNS)
        self.assertEqual(tuple(empty_selection_month_metrics()), SELECTION_MONTH_METRIC_COLUMNS)
        self.assertEqual(tuple(empty_selection_month_composition()), SELECTION_MONTH_COMPOSITION_COLUMNS)
        self.assertEqual(tuple(empty_selection_coverage_summary()), SELECTION_COVERAGE_SUMMARY_COLUMNS)
        self.assertTrue(tables.selection_catalog.empty)
        self.assertEqual(str(tables.selection_month_metrics["tx_count"].dtype), "Int64")
        self.assertEqual(str(tables.selection_month_composition["is_unknown"].dtype), "boolean")

    def test_group_and_name_use_separate_namespaces(self) -> None:
        tables = self.build([{"item_group_id": "Same", "item_name_id": "Same"}])
        catalog = tables.selection_catalog
        self.assertEqual(set(catalog["selection_type"]), {"item_group", "item_name"})
        self.assertEqual(catalog["selection_id"].nunique(), 2)

    def test_same_item_name_is_split_by_parent_group(self) -> None:
        tables = self.build([
            {"product_id": "p3:" + "1" * 64, "item_group_id": "Group A", "item_name_id": "Shared"},
            {"product_id": "p3:" + "2" * 64, "item_group_id": "Group B", "item_name_id": "Shared"},
        ])
        names = tables.selection_catalog.query("selection_type == 'item_name'")
        self.assertEqual(len(names), 2)
        self.assertEqual(set(names["parent_conflict_status"]), {"multiple"})
        self.assertEqual(names["selection_id"].nunique(), 2)

    def test_label_normalization_is_deterministic_and_preserves_punctuation(self) -> None:
        first = self.build([{"item_group_id": " A-B  ", "item_name_id": "Item"}])
        second = self.build([{"item_group_id": "Ａ-B", "item_name_id": "Item"}])
        first_group = first.selection_catalog.query("selection_type == 'item_group'").iloc[0]
        second_group = second.selection_catalog.query("selection_type == 'item_group'").iloc[0]
        self.assertEqual(first_group["normalized_label"], "a-b")
        self.assertEqual(first_group["selection_id"], second_group["selection_id"])

    def test_input_order_does_not_change_tables(self) -> None:
        rows = [
            {"product_id": "p3:" + "1" * 64, "item_group_id": "Group A", "item_name_id": "Item", "src_company_id": "s2"},
            {"product_id": "p3:" + "2" * 64, "item_group_id": "Group A", "item_name_id": "Item", "src_company_id": "s1"},
        ]
        first = self.build(rows)
        second = self.build(list(reversed(rows)))
        self.assertEqual(serialize_class3_analysis(first), serialize_class3_analysis(second))

    def test_supplier_and_receiver_are_recomputed_distinct(self) -> None:
        tables = self.build([
            {"product_id": "p3:" + "1" * 64, "src_company_id": "s1", "dst_company_id": "r1"},
            {"product_id": "p3:" + "2" * 64, "src_company_id": "s1", "dst_company_id": "r2"},
            {"product_id": "p3:" + "3" * 64, "src_company_id": "s2", "dst_company_id": "r2"},
        ])
        group_id = tables.selection_catalog.query("selection_type == 'item_group'").iloc[0]["selection_id"]
        metric = tables.selection_month_metrics.query("selection_id == @group_id").iloc[0]
        self.assertEqual(metric["unique_supplier_count"], 2)
        self.assertEqual(metric["unique_receiver_count"], 2)

    def test_dimension_conflict_becomes_unknown_endpoint(self) -> None:
        tables = self.build([
            {"product_id": "p3:" + "1" * 64, "src_company_id": "s1", "supplier_type": "manufacturer"},
            {"product_id": "p3:" + "2" * 64, "src_company_id": "s1", "supplier_type": "importer"},
        ])
        unknown = tables.selection_month_composition[
            (tables.selection_month_composition["dimension"] == "supplier_type")
            & (tables.selection_month_composition["is_unknown"])
        ]
        self.assertEqual(len(unknown), 2)
        self.assertTrue((unknown["dimension_value"] == "unknown").all())
        self.assertTrue((unknown["endpoint_count"] == 1).all())

    def test_composition_count_matches_its_denominator(self) -> None:
        tables = self.build([
            {"product_id": "p3:" + "1" * 64, "src_company_id": "s1"},
            {"product_id": "p3:" + "2" * 64, "src_company_id": "s2"},
        ])
        composition = tables.selection_month_composition
        totals = composition.groupby(["selection_id", "month", "dimension"])["endpoint_count"].sum()
        denominators = composition.groupby(["selection_id", "month", "dimension"])["denominator_endpoint_count"].first()
        pd.testing.assert_series_equal(totals, denominators, check_names=False)

    def test_decimal_sums_and_coverage_are_exact(self) -> None:
        tables = self.build([
            {"product_id": "p3:" + "1" * 64, "tx_count": 2, "amount_sum_clean": Decimal("1.10"), "amount_valid_row_count": 1},
            {"product_id": "p3:" + "2" * 64, "tx_count": 1, "amount_sum_clean": Decimal("2.20"), "amount_valid_row_count": 1},
        ])
        metric = tables.selection_month_metrics.query("selection_type == 'item_group'").iloc[0]
        self.assertEqual(metric["amount_sum_clean"], Decimal("3.30"))
        self.assertEqual(metric["amount_coverage"], Decimal("0.666667"))

    def test_raw_and_piece_quantities_remain_independent(self) -> None:
        tables = self.build([{"raw_supply_qty_sum": Decimal("3"), "piece_qty_sum": Decimal("30")}])
        metric = tables.selection_month_metrics.query("selection_type == 'item_group'").iloc[0]
        self.assertEqual(metric["raw_supply_qty_sum"], Decimal("3"))
        self.assertEqual(metric["piece_qty_sum"], Decimal("30"))

    def test_missing_month_and_period_coverage_are_explicit(self) -> None:
        tables = self.build([{}], start="202401", end="202403")
        summary = tables.selection_coverage_summary.query("selection_type == 'item_group'").iloc[0]
        self.assertEqual(summary["included_months"], ("202401",))
        self.assertEqual(summary["missing_months"], ("202402", "202403"))
        self.assertEqual(summary["amount_valid_rate"], Decimal("1.000000"))
        self.assertEqual(summary["data_version"], "complete-fingerprint")

    def test_unique_udi_count_is_not_an_output_metric(self) -> None:
        first = self.build([{"unique_udi_count": 1}])
        second = self.build([{"unique_udi_count": 0}])
        self.assertEqual(serialize_class3_analysis(first), serialize_class3_analysis(second))

    def test_serializer_is_deterministic_and_excludes_forbidden_fields(self) -> None:
        payload = serialize_class3_analysis(self.build([{}]))
        self.assertEqual(payload["analysis_schema_version"], CLASS3_ANALYSIS_SCHEMA_VERSION)
        self.assertEqual(payload, serialize_class3_analysis(self.build([{}])))
        rendered = repr(payload)
        for forbidden in ("unique_udi_count", "hhi", "growth", "mcdm", "company_name"):
            self.assertNotIn(forbidden, rendered.casefold())
        metric = payload["selection_month_metrics"][0]
        self.assertEqual(metric["amount_sum_clean"], "1.00")
