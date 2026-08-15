"""Focused synthetic coverage for the read-only turnkey inspection commands."""
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from class_1_anomaly_detection.src.offline_anchor_runner import Class1OfflineAnchorConfig, run_class1_offline_anchor
from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from data_pipeline.offline.class3_analysis_export import Class3SelectionRequest, export_class3_analysis
from data_pipeline.offline.local_analysis_tools import inventory_monthly_fact, publish_class1_web_artifact, verify_class1_artifact, verify_class1_web_artifact, verify_class3_artifact
from data_pipeline.storage.monthly_fact_parquet import write_monthly_fact_partitions


def _fact(months):
    rows = [[month, "synthetic-a", "synthetic-b", f"p3:{i:064d}", "GROUP", "NAME", 1, Decimal("1"), 1, Decimal("2"), 1, Decimal("3"), 1, 1, 1, "manufacturer", "hospital", "11", "26", "synthetic", ""] for i, month in enumerate(months)]
    frame = pd.DataFrame(rows, columns=empty_monthly_fact().columns)
    for column in ("month", "src_company_id", "dst_company_id", "product_id", "item_group_id", "item_name_id", "supplier_type", "receiver_type", "supplier_region", "receiver_region", "source_version", "quality_flags"): frame[column] = frame[column].astype("string")
    for column in ("tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count", "piece_qty_valid_row_count", "unique_udi_count", "active_day_count"): frame[column] = frame[column].astype("Int64")
    return frame


class LocalAnalysisToolsTests(unittest.TestCase):
    def test_inventory_and_verifiers_use_existing_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); parquet = root / "parquet"; write_monthly_fact_partitions(_fact(("202401", "202402", "202403", "202404", "202405", "202406")), parquet)
            inventory = inventory_monthly_fact(parquet_root=parquet, limit=1)
            self.assertEqual(inventory["item_names_parent_scoped"]["values"], [{"parent_item_group": "GROUP", "item_name": "NAME"}])
            public = root / "public"
            export_class3_analysis(parquet_root=parquet, period_start="202401", period_end="202402", selections=(Class3SelectionRequest("item_group", "GROUP"),), web_public_root=public)
            self.assertTrue(verify_class3_artifact(web_public_root=public)["local_only"])
            result = run_class1_offline_anchor(Class1OfflineAnchorConfig(parquet, root / "output", "202406", "synthetic-a", ("11", "26"), "synthetic", 7, 1, 2, 2))
            verified = verify_class1_artifact(output_root=root / "output", anchor_month="202406")
            self.assertEqual(verified["run_status"], result.run_status)
            published = publish_class1_web_artifact(output_root=root / "output", web_public_root=root / "web-public", anchor_month="202406")
            self.assertEqual(published["status"], "written")
            self.assertEqual(verify_class1_web_artifact(web_public_root=root / "web-public", anchor_month="202406", selected_entity_id="synthetic-a")["run_status"], "insufficient_graph")
            self.assertEqual(publish_class1_web_artifact(output_root=root / "output", web_public_root=root / "web-public", anchor_month="202406")["status"], "unchanged")
