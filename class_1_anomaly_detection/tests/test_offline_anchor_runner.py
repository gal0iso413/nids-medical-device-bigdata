from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from class_1_anomaly_detection.src.offline_anchor_runner import (
    MANIFEST_FILENAME,
    ONE_HOP_GRAPH_FILENAME,
    QA_FILENAME,
    SERVICE_FILENAME,
    Class1OfflineAnchorConfig,
    Class1OfflineAnchorRunConflictError,
    Class1OfflineAnchorRunError,
    run_class1_offline_anchor,
)
from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from data_pipeline.storage.monthly_fact_parquet import write_monthly_fact_partitions


def _fact(months, *, self_loops=False):
    rows = []
    for index, month in enumerate(months):
        source, target = ("a", "a") if self_loops else ("a", "b")
        rows.append([
            month, source, target, f"p3:{index:064d}", "group", "name", 1,
            Decimal("12.345678"), 1, Decimal("2.000000"), 1, Decimal("3.000000"), 1,
            1, 1, "manufacturer", "hospital", "11", "26", "fixture-v1", "",
        ])
    frame = pd.DataFrame(rows, columns=empty_monthly_fact().columns)
    for column in (
        "month", "src_company_id", "dst_company_id", "product_id", "item_group_id", "item_name_id",
        "supplier_type", "receiver_type", "supplier_region", "receiver_region", "source_version", "quality_flags",
    ):
        frame[column] = frame[column].astype("string")
    for column in (
        "tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count",
        "piece_qty_valid_row_count", "unique_udi_count", "active_day_count",
    ):
        frame[column] = frame[column].astype("Int64")
    return frame


class OfflineAnchorRunnerTests(unittest.TestCase):
    months = ("202401", "202402", "202403", "202404", "202405", "202406")

    def _roots(self, *, self_loops=False, months=None, fact=None):
        temporary = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        parquet_root = root / "parquet"
        write_monthly_fact_partitions(fact if fact is not None else _fact(months or self.months, self_loops=self_loops), parquet_root)
        return parquet_root, root / "output"

    def _config(self, parquet_root, output_root, **kwargs):
        values = {
            "parquet_root": parquet_root, "output_root": output_root, "anchor_month": "202406",
            "selected_entity_id": "a",
            "region_vocabulary": ("11", "26"), "model_version": "gadnr-test-v1",
            "seed": 7, "minimum_role_sample": 1,
        }
        values.update(kwargs)
        return Class1OfflineAnchorConfig(**values)

    @staticmethod
    def _scorer(features, edge_index):
        return [float(index) + 0.25 for index in range(len(features))]

    def test_six_verified_partitions_are_read_and_injected_scorer_publishes_safe_payloads(self):
        parquet_root, output_root = self._roots()
        with patch("class_1_anomaly_detection.src.offline_anchor_runner.verify_monthly_fact_partition", wraps=__import__("data_pipeline.storage.monthly_fact_parquet", fromlist=["verify_monthly_fact_partition"]).verify_monthly_fact_partition) as verify:
            result = run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)
        self.assertEqual((result.status, result.run_status, verify.call_count), ("written", "completed", 6))
        qa = json.loads((result.run_directory / QA_FILENAME).read_text(encoding="utf-8"))
        service = json.loads((result.run_directory / SERVICE_FILENAME).read_text(encoding="utf-8"))
        self.assertIn("raw_score", qa["qa_results"][0])
        self.assertNotIn("raw_score", json.dumps(service, sort_keys=True))
        self.assertEqual(len(json.loads(result.manifest_path.read_text(encoding="utf-8"))["partition_lineage"]), 6)

    def test_one_hop_graph_keeps_only_selected_inbound_outbound_edges_and_contract_fields(self):
        fact = _fact(self.months)
        extra = _fact(("202404", "202405", "202406"))
        extra.loc[:, "product_id"] = [f"p3:{index + 100:064d}" for index in range(len(extra))]
        extra.loc[:, "src_company_id"] = pd.Series(["b", "a", "c"], dtype="string")
        extra.loc[:, "dst_company_id"] = pd.Series(["a", "c", "d"], dtype="string")
        self_loop = _fact(("202406",), self_loops=True)
        self_loop.loc[:, "product_id"] = "p3:" + "200".zfill(64)
        parquet_root, output_root = self._roots(fact=pd.concat([fact, extra, self_loop], ignore_index=True))
        result = run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)
        payload = json.loads((result.run_directory / "internal-one-hop-graph.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["graph_scope"], "one_hop")
        self.assertEqual({(edge["src_company_id"], edge["dst_company_id"]) for edge in payload["edges"]}, {("a", "b"), ("b", "a"), ("a", "c")})
        self.assertTrue(all("amount_sum_clean" in edge and "raw_supply_qty_sum" in edge and "piece_qty_sum" in edge for edge in payload["edges"]))
        self.assertTrue(all("amount_valid_rate" in edge and "raw_supply_qty_valid_rate" in edge and "piece_qty_valid_rate" in edge for edge in payload["edges"]))
        self.assertNotIn("raw_score", json.dumps(payload, sort_keys=True))
        self.assertNotIn("raw_score", (result.run_directory / SERVICE_FILENAME).read_text(encoding="utf-8"))
        self.assertEqual(payload["graph_summary"]["self_loop_excluded_count"], 1)

    def test_selected_entity_must_be_in_anchor_graph_without_creating_output(self):
        parquet_root, output_root = self._roots()
        with self.assertRaisesRegex(Class1OfflineAnchorRunError, "absent"):
            run_class1_offline_anchor(self._config(parquet_root, output_root, selected_entity_id="missing"), scorer=self._scorer)
        self.assertFalse(output_root.exists())

    def test_missing_month_blocks_before_output(self):
        parquet_root, output_root = self._roots(months=self.months[:-1])
        with self.assertRaisesRegex(Class1OfflineAnchorRunError, "six required"):
            run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)
        self.assertFalse(output_root.exists())

    def test_region_vocabulary_must_be_explicit_and_production_sorted(self):
        parquet_root, output_root = self._roots()
        with self.assertRaisesRegex(Class1OfflineAnchorRunError, "region_vocabulary"):
            run_class1_offline_anchor(self._config(parquet_root, output_root, region_vocabulary=()), scorer=self._scorer)
        with self.assertRaisesRegex(Class1OfflineAnchorRunError, "sorted"):
            run_class1_offline_anchor(self._config(parquet_root, output_root, region_vocabulary=("26", "11")), scorer=self._scorer)

    def test_missing_optional_ml_dependency_is_clear_and_never_installed(self):
        parquet_root, output_root = self._roots()
        with patch("class_1_anomaly_detection.src.model_pipeline.run_gadnr", side_effect=RuntimeError("GAD-NR requires optional PyGOD/torch dependencies")):
            with self.assertRaisesRegex(Class1OfflineAnchorRunError, "optional ML dependency unavailable"):
                run_class1_offline_anchor(self._config(parquet_root, output_root))
        self.assertFalse(output_root.exists())

    def test_deterministic_checksums_and_unchanged_rerun(self):
        parquet_root, output_root = self._roots()
        first = run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)
        second = run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)
        self.assertEqual(second.status, "unchanged")
        manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
        for filename, expected in manifest["output_sha256"].items():
            self.assertEqual(sha256((first.run_directory / filename).read_bytes()).hexdigest(), expected)

    def test_different_config_or_lineage_is_a_conflict(self):
        parquet_root, output_root = self._roots()
        run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)
        with self.assertRaises(Class1OfflineAnchorRunConflictError):
            run_class1_offline_anchor(self._config(parquet_root, output_root, seed=8), scorer=self._scorer)
        with self.assertRaises(Class1OfflineAnchorRunConflictError):
            run_class1_offline_anchor(self._config(parquet_root, output_root, selected_entity_id="b"), scorer=self._scorer)

    def test_matching_payloads_recover_missing_manifest_only(self):
        parquet_root, output_root = self._roots()
        first = run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)
        first.manifest_path.unlink()
        recovered = run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)
        self.assertEqual(recovered.status, "recovered")
        self.assertTrue(recovered.manifest_path.name == MANIFEST_FILENAME)

    def test_nested_output_root_is_blocked(self):
        parquet_root, _ = self._roots()
        with self.assertRaisesRegex(Class1OfflineAnchorRunError, "non-nested"):
            run_class1_offline_anchor(self._config(parquet_root, parquet_root / "output"), scorer=self._scorer)

    def test_insufficient_graph_is_service_safe_without_calling_scorer(self):
        parquet_root, output_root = self._roots()
        def forbidden(*_args):
            raise AssertionError("scorer must not run for an insufficient graph")
        result = run_class1_offline_anchor(self._config(parquet_root, output_root, minimum_edge_count=2), scorer=forbidden)
        self.assertEqual((result.run_status, result.status), ("insufficient_graph", "written"))
        service = json.loads((result.run_directory / SERVICE_FILENAME).read_text(encoding="utf-8"))
        self.assertEqual(service["service_results"], [])
        self.assertNotIn("raw_score", json.dumps(service, sort_keys=True))

    def test_partial_payload_is_not_recovered(self):
        parquet_root, output_root = self._roots()
        run_directory = output_root / "anchor_month=202406"
        run_directory.mkdir(parents=True)
        (run_directory / QA_FILENAME).write_bytes(b"{}")
        with self.assertRaises(Class1OfflineAnchorRunConflictError):
            run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)

    def test_missing_graph_or_graph_checksum_mismatch_is_blocked(self):
        parquet_root, output_root = self._roots()
        first = run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)
        graph_path = first.run_directory / ONE_HOP_GRAPH_FILENAME
        graph_path.unlink()
        with self.assertRaises(Class1OfflineAnchorRunConflictError):
            run_class1_offline_anchor(self._config(parquet_root, output_root), scorer=self._scorer)
