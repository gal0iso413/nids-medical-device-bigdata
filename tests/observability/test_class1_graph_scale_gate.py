from __future__ import annotations

from decimal import Decimal
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

import pandas as pd

from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from data_pipeline.observability.class1_graph_scale_gate import (
    Class1GraphScaleGateConfigError,
    Class1GraphScaleGateError,
    load_class1_graph_scale_gate_config,
    run_class1_graph_scale_gate,
)
from data_pipeline.storage.monthly_fact_parquet import (
    DATASET_NAME,
    FACT_SCHEMA_VERSION,
    write_monthly_fact_partitions,
)

ROOT = Path(__file__).resolve().parents[2]
MONTHS = ("202401", "202402", "202403", "202404", "202405", "202406")
SRC = "SYNTHETIC-GATE-SRC"
DST = "SYNTHETIC-GATE-DST"
PRODUCT = "p3:" + "1".zfill(64)


def _fact(months: tuple[str, ...] = MONTHS) -> pd.DataFrame:
    rows = []
    for month in months:
        rows.append([
            month, SRC, DST, PRODUCT, "group", "name", 1,
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


class Class1GraphScaleGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.gettempdir()) / f"class1-graph-scale-gate-{uuid4().hex}"
        self.temp.mkdir()
        self.parquet_root = self.temp / "monthly-facts"
        write_monthly_fact_partitions(_fact(), self.parquet_root)
        self.config_path = self.temp / "config.json"
        self.report = self.temp / "reports" / "report.json"
        self.report.parent.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def config(self, **overrides: object):
        value: dict[str, object] = {
            "parquet_root": str(self.parquet_root),
            "anchor_month": "202406",
            "region_vocabulary": ["11", "26"],
            "seed": 17,
            "report_label": "synthetic-graph-scale",
            "max_nodes": 50,
            "max_edges": 50,
            "max_peak_rss_bytes": 8 * 1024 * 1024 * 1024,
            "max_gadnr_seconds": 30,
        }
        value.update(overrides)
        self.config_path.write_text(json.dumps(value), encoding="utf-8")
        return load_class1_graph_scale_gate_config(self.config_path)

    @staticmethod
    def _scorer(features, edge_index):
        del edge_index
        return [float(index) + 0.25 for index in range(len(features))]

    def test_pass_with_injected_scorer(self) -> None:
        report = run_class1_graph_scale_gate(self.config(), self.report, scorer=self._scorer)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["fail_reasons"], [])
        self.assertEqual(report["graph"]["node_count"], 2)
        self.assertEqual(report["graph"]["edge_count"], 1)
        self.assertEqual(report["timing"]["gadnr_status"], "completed")
        self.assertFalse(report["graph"]["sliced_by_region"])
        self.assertFalse(report["graph"]["sliced_by_item_group"])
        self.assertFalse(report["training_graph_policy"]["slice_by_region"])
        self.assertFalse(report["training_graph_policy"]["slice_by_item_group"])
        self.assertEqual(report["window_months"], ["202404", "202405", "202406"])
        self.assertEqual(report["required_months"], list(MONTHS))
        if os.name == "nt":
            self.assertIsInstance(report["memory"]["peak_rss_bytes"], int)
            self.assertGreater(report["memory"]["peak_rss_bytes"], 0)

    def test_over_max_nodes_skips_gadnr_without_slicing(self) -> None:
        def boom(features, edge_index):
            raise AssertionError("GAD-NR must not run after a node-ceiling failure")

        report = run_class1_graph_scale_gate(self.config(max_nodes=1), self.report, scorer=boom)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["fail_reasons"], ["over_max_nodes"])
        self.assertEqual(report["graph"]["node_count"], 2)
        self.assertEqual(report["graph"]["edge_count"], 1)
        self.assertEqual(report["timing"]["gadnr_status"], "not_run")
        self.assertIsNone(report["timing"]["gadnr_seconds"])
        self.assertFalse(report["graph"]["sliced_by_region"])
        self.assertFalse(report["graph"]["sliced_by_item_group"])

    def test_report_omits_identifiers_and_paths(self) -> None:
        run_class1_graph_scale_gate(self.config(), self.report, scorer=self._scorer)
        text = self.report.read_text(encoding="utf-8")
        for forbidden in (str(self.temp), getpass.getuser(), SRC, DST, PRODUCT):
            self.assertNotIn(forbidden, text)
        self.assertNotIn('"slice_by_region":true', text.replace(" ", ""))

    def test_config_and_report_must_be_outside_repository(self) -> None:
        with self.assertRaises(Class1GraphScaleGateConfigError):
            load_class1_graph_scale_gate_config(ROOT / "README.md")
        with self.assertRaises(Class1GraphScaleGateConfigError):
            self.config(parquet_root=str(ROOT))
        with self.assertRaises(Class1GraphScaleGateError):
            run_class1_graph_scale_gate(self.config(), ROOT / "class1-graph-scale-gate-report.json", scorer=self._scorer)

    def test_missing_month_errors_before_report(self) -> None:
        shutil.rmtree(self.parquet_root / DATASET_NAME / f"schema_version={FACT_SCHEMA_VERSION}" / "month=202401")
        with self.assertRaises(Class1GraphScaleGateError):
            run_class1_graph_scale_gate(self.config(), self.report, scorer=self._scorer)
        self.assertFalse(self.report.exists())

    def test_cli_fail_closed_over_max_nodes(self) -> None:
        self.config(max_nodes=1)
        result = subprocess.run(
            [
                sys.executable, "-m", "data_pipeline.observability.class1_graph_scale_gate",
                "--config", str(self.config_path), "--report", str(self.report),
            ],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        payload = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["fail_reasons"], ["over_max_nodes"])
        self.assertEqual(payload["timing"]["gadnr_status"], "not_run")
