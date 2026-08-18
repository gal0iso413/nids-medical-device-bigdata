from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import pandas as pd

from class_1_anomaly_detection.src.offline_anchor_runner import (
    ONE_HOP_GRAPH_FILENAME,
    Class1OfflineAnchorConfig,
    run_class1_offline_anchor,
)
from data_pipeline.analysis.class1_lookup_index import build_class1_lookup_index
from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from data_pipeline.ingest.company_display_name import write_company_display_name_directory
from data_pipeline.ingest.nids_supply_excel import SourceLineage, WorkbookSnapshot
from data_pipeline.storage.monthly_fact_parquet import write_monthly_fact_partitions
from services.class1_local_api.app import StaticRootError, create_app, create_integrated_app
from services.class1_local_api.reader import IndexReader, LookupContractError


MONTHS = ("202401", "202402", "202403", "202404", "202405", "202406")


def _fact():
    rows = []
    for index, month in enumerate(MONTHS):
        rows.append([
            month, "a", "b", f"p3:{index:064d}", "group", "name", 1,
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


def _distributor_fact():
    rows = []
    for index, month in enumerate(MONTHS):
        for dist in range(12):
            rows.append([
                month, f"d{dist:02d}", "h", f"p3:{index:02d}{dist:062d}", "group", "name", 1,
                Decimal("12.345678"), 1, Decimal("2.000000"), 1, Decimal("3.000000"), 1,
                1, 1, "판매(임대)업", "의료기관", "11", "26", "fixture-v1", "",
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


def _scorer(features, edge_index):
    del edge_index
    return [float(index) + 0.25 for index in range(len(features))]


class Class1LocalLookupApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.gettempdir()) / f"class1-local-api-{uuid4().hex}"
        self.root.mkdir()
        self.facts = self.root / "facts"
        self.run = self.root / "run"
        self.index = self.root / "index"
        self.static = self.root / "static"
        write_monthly_fact_partitions(_fact(), self.facts)
        run_class1_offline_anchor(
            Class1OfflineAnchorConfig(
                self.facts, self.run, "202406", "a", ("11", "26"), "gadnr-test-v1", 7, 1,
            ),
            scorer=_scorer,
        )
        build_class1_lookup_index(
            fact_root=self.facts, run_root=self.run, output_root=self.index, anchor_month="202406",
        )
        (self.static / "assets").mkdir(parents=True)
        (self.static / "index.html").write_text("<!doctype html><title>Class 1 local</title><div id=app></div>", encoding="utf-8")
        (self.static / "assets" / "app.js").write_text("console.log('local only')", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_lookup_returns_any_indexed_entity_without_training(self) -> None:
        reader = IndexReader.open(self.index)
        try:
            with patch("class_1_anomaly_detection.src.model_pipeline.run_gadnr", side_effect=AssertionError("no training")):
                review_a = reader.review("a")
                review_b = reader.review("b")
                graph_a = reader.relationships("a")
                graph_b = reader.relationships("b")
        finally:
            reader.close()
        self.assertEqual(review_a["run_status"], "completed")
        self.assertEqual(review_a["service_results"][0]["entity_id"], "a")
        self.assertEqual(review_b["service_results"][0]["entity_id"], "b")
        expected = json.loads((self.run / "anchor_month=202406" / ONE_HOP_GRAPH_FILENAME).read_text(encoding="utf-8"))
        graph_nodes = [{key: value for key, value in node.items() if key not in {"display_name", "name_conflict"}} for node in graph_a["nodes"]]
        comparable = {**graph_a, "nodes": graph_nodes}
        self.assertEqual(comparable, expected)
        self.assertTrue(all("display_name" in node and "name_conflict" in node for node in graph_a["nodes"]))
        self.assertEqual(graph_b["selected_entity_id"], "b")
        self.assertEqual(graph_b["graph_scope"], "one_hop")
        self.assertTrue(all(edge["src_company_id"] == "b" or edge["dst_company_id"] == "b" for edge in graph_b["edges"]))
        self.assertNotIn("raw_score", json.dumps(review_a, sort_keys=True))
        self.assertNotIn("raw_score", json.dumps(graph_b, sort_keys=True))

    def test_review_queue_is_empty_without_distributors(self) -> None:
        reader = IndexReader.open(self.index)
        try:
            queue = reader.review_queue()
        finally:
            reader.close()
        self.assertEqual(queue["role_group"], "distributor")
        self.assertEqual(queue["limit"], 10)
        self.assertEqual(queue["eligible_count"], 0)
        self.assertEqual(queue["entities"], [])
        self.assertNotIn("raw_score", json.dumps(queue, sort_keys=True))

    def test_review_queue_returns_top_ten_distributors(self) -> None:
        facts = self.root / "distributor-facts"
        run = self.root / "distributor-run"
        index = self.root / "distributor-index"
        write_monthly_fact_partitions(_distributor_fact(), facts)
        run_class1_offline_anchor(
            Class1OfflineAnchorConfig(
                facts, run, "202406", "d00", ("11", "26"), "gadnr-test-v1", 7, 1,
            ),
            scorer=_scorer,
        )
        write_company_display_name_directory(
            output_root=facts,
            rows=tuple(
                {
                    "entity_id": f"d{dist:02d}",
                    "display_name": f"합성유통{dist:02d}",
                    "observation_count": 2,
                    "distinct_name_count": 1,
                    "name_conflict": False,
                }
                for dist in range(12)
            ) + (
                {
                    "entity_id": "h",
                    "display_name": "합성병원",
                    "observation_count": 2,
                    "distinct_name_count": 1,
                    "name_conflict": False,
                },
            ),
            lineage=SourceLineage(
                adapter_contract_version="1.0.0",
                source_version="fixture-names",
                workbooks=(WorkbookSnapshot("synthetic.xlsx", 1, "a" * 64),),
            ),
        )
        build_class1_lookup_index(
            fact_root=facts, run_root=run, output_root=index, anchor_month="202406",
        )
        reader = IndexReader.open(index)
        try:
            queue = reader.review_queue()
        finally:
            reader.close()
        app = create_app(index)
        paths = {getattr(route, "path", "") for route in app.routes}
        app.state.index_reader.close()
        self.assertIn("/v1/review-queue", paths)
        self.assertEqual(queue["eligible_count"], 12)
        self.assertTrue(queue["truncated"])
        self.assertEqual(len(queue["entities"]), 10)
        self.assertEqual(queue["entities"][0]["display_name"], "합성유통11")
        self.assertEqual([item["rank"] for item in queue["entities"]], list(range(1, 11)))
        self.assertTrue(all(item["role_group"] == "distributor" for item in queue["entities"]))
        self.assertGreater(
            queue["entities"][0]["review_priority_percentile"],
            queue["entities"][-1]["review_priority_percentile"],
        )
        self.assertNotIn("raw_score", json.dumps(queue, sort_keys=True))
        self.assertNotIn("합성병원", json.dumps(queue, ensure_ascii=False))

    def test_unknown_or_invalid_entity_is_rejected(self) -> None:
        reader = IndexReader.open(self.index)
        try:
            with self.assertRaises(LookupContractError):
                reader.review("missing")
            with self.assertRaises(LookupContractError):
                reader.relationships("../secret")
        finally:
            reader.close()

    def test_app_factory_and_static_root_guards(self) -> None:
        app = create_app(self.index)
        self.assertEqual(app.state.index_reader.index.entity_count, 2)
        app.state.index_reader.close()
        create_integrated_app(self.index, self.static)
        with self.assertRaises(StaticRootError):
            create_integrated_app(self.index, self.root / "missing")
        (self.static / "generated").mkdir()
        (self.static / "generated" / "raw.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(StaticRootError):
            create_integrated_app(self.index, self.static)

    def test_catalog_matches_korean_display_names(self) -> None:
        write_company_display_name_directory(
            output_root=self.facts,
            rows=(
                {
                    "entity_id": "a",
                    "display_name": "알파의료",
                    "observation_count": 2,
                    "distinct_name_count": 1,
                    "name_conflict": False,
                },
                {
                    "entity_id": "b",
                    "display_name": "베타병원",
                    "observation_count": 2,
                    "distinct_name_count": 1,
                    "name_conflict": False,
                },
            ),
            lineage=SourceLineage(
                adapter_contract_version="1.0.0",
                source_version="fixture-names",
                workbooks=(WorkbookSnapshot("synthetic.xlsx", 1, "a" * 64),),
            ),
        )
        named_index = self.root / "named-index"
        build_class1_lookup_index(
            fact_root=self.facts, run_root=self.run, output_root=named_index, anchor_month="202406",
        )
        reader = IndexReader.open(named_index)
        try:
            catalog = reader.catalog("알파")
            graph = reader.relationships("a")
        finally:
            reader.close()
        self.assertEqual(catalog["match_count"], 1)
        self.assertEqual(catalog["entities"][0]["display_name"], "알파의료")
        selected = next(node for node in graph["nodes"] if node["selected"])
        self.assertEqual(selected["display_name"], "알파의료")
        with self.assertRaises(LookupContractError):
            reader = IndexReader.open(named_index)
            try:
                reader.catalog("../secret")
            finally:
                reader.close()

    def test_service_source_does_not_train_or_open_excel(self) -> None:
        root = Path(__file__).resolve().parents[2] / "services" / "class1_local_api"
        text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
        for forbidden in ("run_gadnr", "pygod", "torch", "openpyxl", "read_excel"):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("/v1/entities?query", text)
        self.assertIn("/v1/catalog/entities", text)
        self.assertIn("/v1/review-queue", text)
