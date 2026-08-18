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
import pyarrow.parquet as pq

from class_1_anomaly_detection.src.offline_anchor_runner import (
    ONE_HOP_GRAPH_FILENAME,
    Class1OfflineAnchorConfig,
    run_class1_offline_anchor,
)
from data_pipeline.analysis.class1_lookup_index import (
    Class1LookupIndexConflictError,
    Class1LookupIndexError,
    build_class1_lookup_index,
)
from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from data_pipeline.ingest.company_display_name import write_company_display_name_directory
from data_pipeline.ingest.nids_supply_excel import SourceLineage, WorkbookSnapshot
from data_pipeline.storage.monthly_fact_parquet import write_monthly_fact_partitions


MONTHS = ("202401", "202402", "202403", "202404", "202405", "202406")


def _fact(months=MONTHS):
    rows = []
    for index, month in enumerate(months):
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


def _scorer(features, edge_index):
    del edge_index
    return [float(index) + 0.25 for index in range(len(features))]


class Class1LookupIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.gettempdir()) / f"class1-lookup-index-{uuid4().hex}"
        self.root.mkdir()
        self.facts = self.root / "facts"
        self.run = self.root / "run"
        self.index = self.root / "index"
        write_monthly_fact_partitions(_fact(), self.facts)
        run_class1_offline_anchor(
            Class1OfflineAnchorConfig(
                self.facts, self.run, "202406", "a", ("11", "26"), "gadnr-test-v1", 7, 1,
            ),
            scorer=_scorer,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_index_covers_every_graph_entity_without_raw_scores(self) -> None:
        result = build_class1_lookup_index(
            fact_root=self.facts, run_root=self.run, output_root=self.index, anchor_month="202406",
        )
        self.assertEqual(result.status, "written")
        self.assertEqual(result.row_counts["entities"], 2)
        self.assertEqual(result.row_counts["edges"], 1)
        self.assertEqual(result.row_counts["names"], 2)
        text = result.manifest_path.read_text(encoding="utf-8")
        self.assertNotIn("raw_score", text)
        self.assertIn('"trains_on_request":false', text.replace(" ", ""))
        self.assertIn("schema_version=1.2.0", str(result.output_path))
        self.assertTrue(result.output_path.name.startswith("anchor_month="))
        catalog = json.loads((result.output_path.parent / "_catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["available_anchor_months"], ["202406"])
        self.assertEqual(catalog["default_anchor_month"], "202406")
        self.assertFalse(catalog["trains_on_request"])
        unchanged = build_class1_lookup_index(
            fact_root=self.facts, run_root=self.run, output_root=self.index, anchor_month="202406",
        )
        self.assertEqual(unchanged.status, "unchanged")

    def test_overlap_and_incomplete_runs_are_rejected(self) -> None:
        with self.assertRaises(Class1LookupIndexError):
            build_class1_lookup_index(
                fact_root=self.facts, run_root=self.run, output_root=self.facts, anchor_month="202406",
            )
        (self.run / "anchor_month=202406" / "internal-service.json").unlink()
        with self.assertRaises(Class1LookupIndexError):
            build_class1_lookup_index(
                fact_root=self.facts, run_root=self.run, output_root=self.index, anchor_month="202406",
            )

    def test_different_content_is_a_conflict(self) -> None:
        build_class1_lookup_index(
            fact_root=self.facts, run_root=self.run, output_root=self.index, anchor_month="202406",
        )
        other_facts = self.root / "facts-b"
        other_run = self.root / "run-b"
        extra = _fact()
        extra.loc[:, "dst_company_id"] = pd.Series(["c"] * len(extra), dtype="string")
        write_monthly_fact_partitions(extra, other_facts)
        run_class1_offline_anchor(
            Class1OfflineAnchorConfig(
                other_facts, other_run, "202406", "a", ("11", "26"), "gadnr-test-v1", 7, 1,
            ),
            scorer=_scorer,
        )
        with self.assertRaises(Class1LookupIndexConflictError):
            build_class1_lookup_index(
                fact_root=other_facts, run_root=other_run, output_root=self.index, anchor_month="202406",
            )

    def test_index_joins_korean_display_names_without_using_them_as_ids(self) -> None:
        write_company_display_name_directory(
            output_root=self.facts,
            rows=(
                {
                    "entity_id": "a",
                    "display_name": "알파의료",
                    "observation_count": 3,
                    "distinct_name_count": 1,
                    "name_conflict": False,
                },
                {
                    "entity_id": "b",
                    "display_name": "베타병원",
                    "observation_count": 3,
                    "distinct_name_count": 2,
                    "name_conflict": True,
                },
            ),
            lineage=SourceLineage(
                adapter_contract_version="1.0.0",
                source_version="fixture-names",
                workbooks=(WorkbookSnapshot("공급내역보고자료(20240601~20240610).xlsx", 1, "a" * 64),),
            ),
            month="202406",
        )
        result = build_class1_lookup_index(
            fact_root=self.facts, run_root=self.run, output_root=self.index, anchor_month="202406",
        )
        self.assertEqual(result.status, "written")
        names = pq.read_table(result.output_path / "names.parquet").to_pydict()
        mapped = dict(zip(names["entity_id"], names["display_name"], strict=True))
        self.assertEqual(mapped["a"], "알파의료")
        self.assertEqual(mapped["b"], "베타병원")
        self.assertIn("name_directory_fingerprint", result.manifest_path.read_text(encoding="utf-8"))

    def test_second_anchor_is_a_new_partition(self) -> None:
        build_class1_lookup_index(
            fact_root=self.facts, run_root=self.run, output_root=self.index, anchor_month="202406",
        )
        extra = _fact(MONTHS + ("202407",))
        write_monthly_fact_partitions(extra, self.facts)
        run_class1_offline_anchor(
            Class1OfflineAnchorConfig(
                self.facts, self.run, "202407", "a", ("11", "26"), "gadnr-test-v1", 7, 1,
            ),
            scorer=_scorer,
        )
        second = build_class1_lookup_index(
            fact_root=self.facts, run_root=self.run, output_root=self.index, anchor_month="202407",
        )
        self.assertEqual(second.status, "written")
        catalog = json.loads((second.output_path.parent / "_catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["available_anchor_months"], ["202406", "202407"])
        self.assertEqual(catalog["default_anchor_month"], "202407")
        self.assertTrue((second.output_path.parent / "anchor_month=202406" / "entities.parquet").is_file())
        self.assertTrue((second.output_path / "entities.parquet").is_file())
