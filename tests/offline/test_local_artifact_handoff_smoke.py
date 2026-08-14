"""Synthetic-only smoke test for the Python-to-local-web JSON handoff."""
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from class_1_anomaly_detection.src.offline_anchor_runner import Class1OfflineAnchorConfig, run_class1_offline_anchor
from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from data_pipeline.offline.class3_analysis_export import Class3SelectionRequest, export_class3_analysis
from data_pipeline.storage.monthly_fact_parquet import write_monthly_fact_partitions


def synthetic_fact(months):
    rows = []
    for index, month in enumerate(months):
        rows.append([month, "synthetic-a", "synthetic-b", f"p3:{index:064d}", "SYNTHETIC_GROUP", "SYNTHETIC_ITEM", 1, Decimal("1.000000"), 1, Decimal("2.000000"), 1, Decimal("3.000000"), 1, 1, 1, "manufacturer", "hospital", "11", "26", "synthetic-handoff", ""])
    frame = pd.DataFrame(rows, columns=empty_monthly_fact().columns)
    for column in ("month","src_company_id","dst_company_id","product_id","item_group_id","item_name_id","supplier_type","receiver_type","supplier_region","receiver_region","source_version","quality_flags"): frame[column] = frame[column].astype("string")
    for column in ("tx_count","amount_valid_row_count","raw_supply_qty_valid_row_count","piece_qty_valid_row_count","unique_udi_count","active_day_count"): frame[column] = frame[column].astype("Int64")
    return frame


class LocalArtifactHandoffSmokeTests(unittest.TestCase):
    def test_existing_exporter_and_runner_produce_web_local_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); parquet = root / "parquet"; write_monthly_fact_partitions(synthetic_fact(("202401","202402","202403","202404","202405","202406")), parquet)
            public = root / "public"
            export_class3_analysis(parquet_root=parquet, period_start="202401", period_end="202402", selections=(Class3SelectionRequest("item_group", "SYNTHETIC_GROUP"),), web_public_root=public)
            class3 = json.loads((public / "generated" / "class3-analysis.json").read_text())
            self.assertEqual(class3["analysis_schema_version"], "1.0.0")
            self.assertEqual(class3["local_export"]["publication_scope"], "local_only")
            result = run_class1_offline_anchor(Class1OfflineAnchorConfig(parquet, root / "output", "202406", "synthetic-a", ("11","26"), "synthetic", 7, 1, 2, 2))
            service = json.loads((result.run_directory / "internal-service.json").read_text())
            graph = json.loads((result.run_directory / "internal-one-hop-graph.json").read_text())
            self.assertEqual(service["run_status"], "insufficient_graph")
            self.assertEqual(service["service_results"], [])
            self.assertEqual(graph["selected_entity_id"], "synthetic-a")
            self.assertNotIn("raw_score", json.dumps(service) + json.dumps(graph))
