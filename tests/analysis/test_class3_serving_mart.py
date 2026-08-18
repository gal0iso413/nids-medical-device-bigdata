from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import pyarrow.parquet as pq
import pandas as pd

from data_pipeline.analysis.class3_serving_mart import (
    Class3ServingMartConflictError,
    Class3ServingMartError,
    MANIFEST_FILENAME,
    SERVING_MART_DATASET_NAME,
    SERVING_MART_SCHEMA_VERSION,
    build_class3_serving_marts,
)
from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from data_pipeline.storage.monthly_fact_parquet import write_monthly_fact_partitions


def synthetic_fact(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults: dict[str, object] = {
        "month": "202401", "src_company_id": "supplier-secret-1", "dst_company_id": "receiver-secret-1",
        "product_id": "p3:" + "1" * 64, "item_group_id": "Group A", "item_name_id": "Shared Item",
        "tx_count": 1, "amount_sum_clean": Decimal("10.000000"), "amount_valid_row_count": 1,
        "raw_supply_qty_sum": Decimal("2.000000"), "raw_supply_qty_valid_row_count": 1,
        "piece_qty_sum": Decimal("3.000000"), "piece_qty_valid_row_count": 1,
        "unique_udi_count": 1, "active_day_count": 1, "supplier_type": "manufacturer",
        "receiver_type": "hospital", "supplier_region": "11", "receiver_region": "26",
        "source_version": "synthetic-source", "quality_flags": "source_flag",
    }
    frame = pd.concat(
        [empty_monthly_fact(), pd.DataFrame([{**defaults, **row} for row in rows])],
        ignore_index=True,
    )
    string_columns = (
        "month", "src_company_id", "dst_company_id", "product_id", "item_group_id", "item_name_id",
        "supplier_type", "receiver_type", "supplier_region", "receiver_region", "source_version", "quality_flags",
    )
    count_columns = (
        "tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count",
        "piece_qty_valid_row_count", "unique_udi_count", "active_day_count",
    )
    for column in string_columns:
        frame[column] = frame[column].astype("string")
    for column in count_columns:
        frame[column] = frame[column].astype("Int64")
    return frame


class Class3ServingMartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="class3-serving-mart-"))
        self.fact_root = self.root / "facts"
        self.output_root = self.root / "marts"
        self.p1 = "p3:" + "1" * 64
        self.p2 = "p3:" + "2" * 64
        self.p3 = "p3:" + "3" * 64
        write_monthly_fact_partitions(synthetic_fact([
            {"product_id": self.p1, "src_company_id": "supplier-secret-1", "dst_company_id": "receiver-secret-1", "tx_count": 2, "amount_sum_clean": Decimal("10.000000")},
            {"product_id": self.p1, "src_company_id": "supplier-secret-2", "dst_company_id": "receiver-secret-1", "tx_count": 3, "amount_sum_clean": Decimal("20.000000"), "supplier_region": "27"},
            {"product_id": self.p2, "src_company_id": "supplier-secret-1", "dst_company_id": "receiver-secret-2", "tx_count": 1, "amount_sum_clean": Decimal("5.000000"), "item_name_id": "Other Item"},
            {"product_id": self.p3, "src_company_id": "supplier-secret-3", "dst_company_id": "receiver-secret-3", "item_group_id": "Group B", "item_name_id": "Shared Item", "amount_sum_clean": None, "amount_valid_row_count": 0, "supplier_type": None, "quality_flags": ""},
            {"product_id": self.p1, "month": "202402", "src_company_id": "supplier-secret-1", "dst_company_id": "receiver-secret-3", "tx_count": 4, "amount_sum_clean": Decimal("7.000000"), "raw_supply_qty_sum": Decimal("100.000000")},
        ]), self.fact_root)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def build(self, **kwargs: object):
        return build_class3_serving_marts(
            fact_root=self.fact_root, output_root=self.output_root,
            period_start="202401", period_end="202402", **kwargs,
        )

    def table(self, name: str):
        root = self.output_root / SERVING_MART_DATASET_NAME / f"schema_version={SERVING_MART_SCHEMA_VERSION}"
        return pq.read_table(root / f"{name}.parquet").to_pylist()

    def test_verified_partitions_build_exact_marts_and_preserve_decimals(self) -> None:
        result = self.build()
        self.assertEqual(result.status, "written")
        product_month = self.table("product_month")
        january_p1 = next(row for row in product_month if row["month"] == "202401" and row["product_id"] == self.p1)
        self.assertEqual(january_p1["amount_sum_clean"], Decimal("30.000000"))
        self.assertEqual(january_p1["supplier_count_distinct"], 2)
        self.assertEqual(january_p1["receiver_count_distinct"], 1)
        self.assertEqual(january_p1["unique_udi_count_sum"], 2)
        february_p1 = next(row for row in product_month if row["month"] == "202402" and row["product_id"] == self.p1)
        self.assertEqual(february_p1["raw_supply_qty_sum"], Decimal("100.000000"))
        self.assertIsNone(next(row for row in product_month if row["product_id"] == self.p3)["amount_sum_clean"])
        group = next(row for row in self.table("item_group_month") if row["month"] == "202401" and row["item_group_id"] == "Group A")
        self.assertEqual(group["amount_sum_clean"], Decimal("35.000000"))
        self.assertEqual(group["supplier_count_distinct"], 2)  # Not 2 + 1 from product rows.
        self.assertEqual(group["receiver_count_distinct"], 2)

    def test_catalog_parent_scope_endpoint_privacy_and_coverage_semantics(self) -> None:
        self.build()
        catalog = self.table("product_catalog")
        self.assertEqual(
            {(row["item_group_id"], row["item_name_id"]) for row in catalog if row["item_name_id"] == "Shared Item"},
            {("Group A", "Shared Item"), ("Group B", "Shared Item")},
        )
        endpoint_path = self.output_root / SERVING_MART_DATASET_NAME / f"schema_version={SERVING_MART_SCHEMA_VERSION}" / "endpoint_composition.parquet"
        endpoint_bytes = endpoint_path.read_bytes()
        self.assertNotIn(b"supplier-secret", endpoint_bytes)
        self.assertNotIn(b"receiver-secret", endpoint_bytes)
        self.assertNotIn("src_company_id", pq.read_schema(endpoint_path).names)
        self.assertNotIn("dst_company_id", pq.read_schema(endpoint_path).names)
        coverage = next(row for row in self.table("coverage") if row["month"] == "202401")
        self.assertEqual(coverage["aggregate_observation_count"], 4)
        self.assertEqual(coverage["supplier_type_valid_tx_count"], 6)
        self.assertAlmostEqual(coverage["supplier_type_coverage_ratio"], 6 / 7)
        self.assertEqual(coverage["quality_flags"], "source_flag")
        january_group_receiver = next(
            row for row in self.table("endpoint_composition")
            if row["month"] == "202401" and row["product_scope"] == "item_group"
            and row["product_scope_id"] == "Group A" and row["endpoint"] == "receiver"
            and row["dimension"] == "type" and row["dimension_value"] == "hospital"
        )
        self.assertEqual(january_group_receiver["entity_count_distinct"], 2)
        self.assertEqual(january_group_receiver["tx_count"], 6)
        membership_path = endpoint_path.parent / "endpoint_membership.parquet"
        membership_bytes = membership_path.read_bytes()
        self.assertNotIn(b"supplier-secret", membership_bytes)
        self.assertNotIn(b"receiver-secret", membership_bytes)
        self.assertNotIn("src_company_id", pq.read_schema(membership_path).names)
        self.assertNotIn("dst_company_id", pq.read_schema(membership_path).names)
        self.assertNotIn("entity_id", pq.read_schema(membership_path).names)

    def test_canonical_manifest_is_deterministic_and_safe(self) -> None:
        first = self.build()
        manifest_bytes = first.manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        self.assertEqual(manifest_bytes, json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        self.assertEqual(manifest["fact_schema_version"], "1.0.0")
        self.assertEqual([entry["month"] for entry in manifest["source_partitions"]], ["202401", "202402"])
        self.assertNotIn(str(self.root), manifest_bytes.decode("utf-8"))
        self.assertNotIn("supplier-secret", manifest_bytes.decode("utf-8"))
        self.assertEqual(self.build().status, "unchanged")
        self.assertEqual(manifest_bytes, first.manifest_path.read_bytes())

    def test_different_content_conflicts_and_staging_is_cleaned(self) -> None:
        self.build()
        different = self.root / "different-facts"
        write_monthly_fact_partitions(synthetic_fact([
            {"product_id": self.p1, "amount_sum_clean": Decimal("999.000000")},
            {"product_id": self.p1, "month": "202402", "amount_sum_clean": Decimal("7.000000")},
        ]), different)
        with self.assertRaises(Class3ServingMartConflictError):
            build_class3_serving_marts(fact_root=different, output_root=self.output_root, period_start="202401", period_end="202402")
        final_dir = self.output_root / SERVING_MART_DATASET_NAME / f"schema_version={SERVING_MART_SCHEMA_VERSION}"
        self.assertEqual(list(final_dir.parent.glob(".schema_version=*.tmp-*")), [])

    def test_invalid_period_missing_input_has_bounded_diagnostics_root_overlap_and_failed_staging_are_safe(self) -> None:
        with self.assertRaisesRegex(Class3ServingMartError, "period_start"):
            build_class3_serving_marts(fact_root=self.fact_root, output_root=self.root / "bad", period_start="202402", period_end="202401")
        with self.assertRaisesRegex(Class3ServingMartError, "partitions must verify") as raised:
            build_class3_serving_marts(fact_root=self.fact_root, output_root=self.root / "missing", period_start="202401", period_end="202403")
        self.assertNotIn(str(self.root), str(raised.exception))
        self.assertNotIn("supplier-secret", str(raised.exception))
        with self.assertRaisesRegex(Class3ServingMartError, "must not overlap fact_root"):
            build_class3_serving_marts(fact_root=self.fact_root, output_root=self.fact_root, period_start="202401", period_end="202402")
        with self.assertRaisesRegex(Class3ServingMartError, "must not overlap checkpoint_root"):
            build_class3_serving_marts(fact_root=self.fact_root, output_root=self.root / "checkpoint", checkpoint_root=self.root / "checkpoint", period_start="202401", period_end="202402")
        import data_pipeline.analysis.class3_serving_mart as builder
        failed_root = self.root / "failed"
        with patch.object(builder, "_copy_query", side_effect=OSError("synthetic write failure")):
            with self.assertRaises(Class3ServingMartError):
                build_class3_serving_marts(fact_root=self.fact_root, output_root=failed_root, period_start="202401", period_end="202402")
        parent = failed_root / SERVING_MART_DATASET_NAME
        self.assertEqual(list(parent.glob(".schema_version=*.tmp-*")) if parent.exists() else [], [])

    def test_reader_returns_tx_hhi_and_overlap_without_endpoint_hashes(self) -> None:
        from services.class3_local_api.reader import MartReader
        from services.class3_local_api.schemas import ComparisonSelection

        self.build()
        reader = MartReader.open(self.output_root)
        try:
            result = reader.comparison("202401", "202402", [
                ComparisonSelection(selection_type="item_group", item_group_id="Group A"),
                ComparisonSelection(selection_type="item_group", item_group_id="Group B"),
            ])
        finally:
            reader.close()
        january = next(
            row for row in result["selection_concentration"]
            if row["item_group_id"] == "Group A" and row["month"] == "202401"
        )
        self.assertEqual(january["supplier_hhi_tx"], "0.500000")
        self.assertEqual(january["supplier_count"], 2)
        composition = next(
            row for row in result["endpoint_composition"]
            if row["month"] == "202401" and row["product_scope"] == "item_group"
            and row["product_scope_id"] == "Group A" and row["endpoint"] == "receiver"
            and row["dimension"] == "type" and row["dimension_value"] == "hospital"
        )
        self.assertEqual(composition["tx_count"], 6)
        self.assertEqual(result["portfolio_overlap"]["supplier_union_count"], 3)
        self.assertEqual(result["portfolio_overlap"]["pairs"][0]["supplier_intersection_count"], 0)
        rendered = json.dumps(result)
        self.assertNotIn("entity_hash", rendered)
        self.assertNotIn("supplier-secret", rendered)


if __name__ == "__main__":
    unittest.main()
