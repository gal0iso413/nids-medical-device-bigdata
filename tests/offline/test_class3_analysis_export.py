from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import pandas as pd

from data_pipeline.aggregates.class3_analysis import build_class3_analysis
from data_pipeline.contracts.class3_analysis import serialize_class3_analysis
from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from data_pipeline.offline.class3_analysis_export import (
    Class3OfflineExportConflictError,
    Class3SelectionRequest,
    export_class3_analysis,
)
from data_pipeline.storage.monthly_fact_parquet import write_monthly_fact_partitions


def fact(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults: dict[str, object] = {
        "month": "202401", "src_company_id": "s", "dst_company_id": "r",
        "product_id": "p3:" + "0" * 64, "item_group_id": "Group A", "item_name_id": "Item A",
        "tx_count": 1, "amount_sum_clean": Decimal("1"), "amount_valid_row_count": 1,
        "raw_supply_qty_sum": Decimal("2"), "raw_supply_qty_valid_row_count": 1,
        "piece_qty_sum": Decimal("3"), "piece_qty_valid_row_count": 1,
        "unique_udi_count": 1, "active_day_count": 1, "supplier_type": "manufacturer",
        "receiver_type": "hospital", "supplier_region": "11", "receiver_region": "26",
        "source_version": "synthetic-v1", "quality_flags": "",
    }
    frame = pd.concat([empty_monthly_fact(), pd.DataFrame([{**defaults, **row} for row in rows])], ignore_index=True)
    for column in ("month", "src_company_id", "dst_company_id", "product_id", "item_group_id", "item_name_id", "supplier_type", "receiver_type", "supplier_region", "receiver_region", "source_version", "quality_flags"):
        frame[column] = frame[column].astype("string")
    for column in ("tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count", "piece_qty_valid_row_count", "unique_udi_count", "active_day_count"):
        frame[column] = frame[column].astype("Int64")
    return frame


class Class3OfflineExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="c3-export-"))
        self.store = self.root / "store"
        self.public = self.root / "web-public"
        write_monthly_fact_partitions(fact([
            {"product_id": "p3:" + "1" * 64, "month": "202401", "item_group_id": "Group A", "item_name_id": "Item A"},
            {"product_id": "p3:" + "2" * 64, "month": "202402", "item_group_id": "Group A", "item_name_id": "Item A"},
            {"product_id": "p3:" + "3" * 64, "month": "202401", "item_group_id": "Group B", "item_name_id": "Item B"},
            {"product_id": "p3:" + "4" * 64, "month": "202402", "item_group_id": "Group B", "item_name_id": "Item B"},
        ]), self.store)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def export(self, **kwargs):
        return export_class3_analysis(
            parquet_root=self.store, period_start="202401", period_end="202402",
            selections=(Class3SelectionRequest("item_group", "Group A"),), web_public_root=self.public,
            **kwargs,
        )

    def payload(self) -> dict[str, object]:
        return json.loads((self.public / "generated" / "class3-analysis.json").read_text(encoding="utf-8"))

    def test_multiple_selection_period_serializer_and_adapter_shape(self) -> None:
        result = export_class3_analysis(
            parquet_root=self.store, period_start="202401", period_end="202402", web_public_root=self.public,
            selections=(Class3SelectionRequest("item_group", "Group A"), Class3SelectionRequest("item_group", "Group B")),
        )
        payload = self.payload()
        self.assertEqual(result.export_state, "available")
        self.assertEqual(payload["analysis_schema_version"], "1.0.0")
        self.assertEqual({row["label"] for row in payload["selection_catalog"]}, {"Group A", "Group B"})
        self.assertEqual(payload["local_export"]["publication_scope"], "local_only")

    def test_payload_retains_existing_serializer_table_contract_except_local_metadata(self) -> None:
        self.export()
        payload = self.payload()
        expected = serialize_class3_analysis(build_class3_analysis(
            fact([{ "product_id": "p3:" + "1" * 64, "month": "202401" }]),
            period_start="202401", period_end="202402", data_version="test",
        ))
        self.assertEqual(set(payload) - {"local_export"}, set(expected))
        self.assertEqual(set(payload["selection_month_metrics"][0]), set(expected["selection_month_metrics"][0]))
        self.assertEqual(set(payload["selection_month_composition"][0]), set(expected["selection_month_composition"][0]))
        self.assertEqual(set(payload["selection_coverage_summary"][0]), set(expected["selection_coverage_summary"][0]))

    def test_deterministic_atomic_publish_and_unchanged_rerun(self) -> None:
        first = self.export()
        first_bytes = first.output_path.read_bytes()
        second = self.export()
        self.assertEqual((first.status, second.status), ("written", "unchanged"))
        self.assertEqual(first_bytes, second.output_path.read_bytes())
        self.assertFalse(list((self.public / "generated").glob(".*.tmp")))

    def test_lineage_conflict_blocks_overwrite(self) -> None:
        self.export()
        other_store = self.root / "other-store"
        write_monthly_fact_partitions(fact([
            {"product_id": "p3:" + "5" * 64, "month": "202401", "item_group_id": "Group A", "source_version": "synthetic-v2"},
            {"product_id": "p3:" + "6" * 64, "month": "202402", "item_group_id": "Group A", "source_version": "synthetic-v2"},
        ]), other_store)
        with self.assertRaises(Class3OfflineExportConflictError):
            export_class3_analysis(
                parquet_root=other_store, period_start="202401", period_end="202402", web_public_root=self.public,
                selections=(Class3SelectionRequest("item_group", "Group A"),),
            )

    def test_item_name_selection_keeps_its_parent_scope(self) -> None:
        result = export_class3_analysis(
            parquet_root=self.store, period_start="202401", period_end="202402", web_public_root=self.public,
            selections=(Class3SelectionRequest("item_name", "Item B", "Group B"),),
        )
        catalog = self.payload()["selection_catalog"]
        self.assertEqual(result.export_state, "available")
        self.assertEqual([(row["selection_type"], row["label"], row["parent_item_group_label"]) for row in catalog], [("item_name", "Item B", "Group B")])

    def test_missing_month_marks_coverage_insufficient(self) -> None:
        result = export_class3_analysis(
            parquet_root=self.store, period_start="202401", period_end="202403", web_public_root=self.public,
            selections=(Class3SelectionRequest("item_group", "Group A"),),
        )
        summary = self.payload()["selection_coverage_summary"][0]
        self.assertEqual(result.export_state, "insufficient_coverage")
        self.assertIn("local_export_coverage_insufficient", summary["quality_flags"])
        self.assertEqual(summary["missing_months"], ["202403"])

    def test_empty_selection_suppressed_and_not_available_payloads(self) -> None:
        empty = export_class3_analysis(parquet_root=self.store, period_start="202401", period_end="202402", selections=(), web_public_root=self.public)
        self.assertEqual(empty.export_state, "not_available")
        self.assertEqual(self.payload()["local_export"]["reason"], "selection_required")
        no_rows_public = self.root / "no-rows-public"
        no_rows = export_class3_analysis(parquet_root=self.store, period_start="202401", period_end="202402", selections=(Class3SelectionRequest("item_group", "Absent Group"),), web_public_root=no_rows_public)
        self.assertEqual(no_rows.export_state, "not_available")
        self.assertEqual(json.loads((no_rows_public / "generated" / "class3-analysis.json").read_text())["local_export"]["reason"], "no_rows_for_requested_selections")
        second_public = self.root / "second-public"
        suppressed = export_class3_analysis(parquet_root=self.store, period_start="202401", period_end="202402", selections=(Class3SelectionRequest("item_group", "Group A"),), web_public_root=second_public, availability_state="suppressed")
        self.assertEqual(suppressed.export_state, "suppressed")
        self.assertEqual(json.loads((second_public / "generated" / "class3-analysis.json").read_text())["local_export"]["public_policy_state"], "not_applied")
