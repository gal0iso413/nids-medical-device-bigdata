from __future__ import annotations

import getpass
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from openpyxl import Workbook

from data_pipeline.ingest.nids_supply_excel import HEADER_ALIASES, TRANSACTION_TYPE_MAP
from data_pipeline.observability.scale_preflight import ScalePreflightConfigError, ScalePreflightError, atomic_write_canonical_json, load_scale_preflight_config, run_scale_preflight

ROOT = Path(__file__).resolve().parents[2]
FIELDS = tuple(HEADER_ALIASES)
HEADERS = tuple(HEADER_ALIASES[field][0] for field in FIELDS)
SUPPLY = next(key for key, value in TRANSACTION_TYPE_MAP.items() if value == "SUPPLY")


def row(number: int, valid: bool = True) -> list[object]:
    values = {"supply_date":"20260115", "src_company_id":str(number) if valid else None, "dst_company_id":"20", "hospital_id":None, "item_serial":"1", "model_serial":"2", "udi_serial":"3", "item_group_id":"SYNTHETIC-GROUP-SECRET", "item_name_id":"SYNTHETIC-ITEM-SECRET", "transaction_type":SUPPLY, "amount_clean":"100", "raw_supply_qty":"2", "package_qty":"5", "piece_qty":"10", "udi":"SYNTHETIC-UDI-SECRET", "supplier_type":"SYNTHETIC-SUPPLIER-SECRET", "receiver_type":"SYNTHETIC-RECEIVER-SECRET", "supplier_region":"01", "receiver_region":"02", "client_code":"100", "base_month":"202601", "work_serial":str(1000 + number), "supply_serial":str(2000 + number), "reported_composite_key":f"synthetic-secret-{number}"}
    return [values[field] for field in FIELDS]


def workbook(path: Path, rows: list[list[object]]) -> None:
    book = Workbook(); sheet = book.active; sheet.title = "data"; sheet.append(HEADERS)
    for item in rows: sheet.append(item)
    book.save(path); book.close()


class ScalePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.gettempdir()) / f"scale-preflight-{uuid4().hex}"
        self.temp.mkdir(); self.first = self.temp / "a.xlsx"; self.second = self.temp / "b.xlsx"
        workbook(self.first, [row(1), row(2), row(3)]); workbook(self.second, [row(4, False), row(5)])
        self.config_path = self.temp / "config.json"; self.report = self.temp / "reports" / "report.json"; self.report.parent.mkdir()

    def tearDown(self) -> None: shutil.rmtree(self.temp, ignore_errors=True)

    def config(self, **overrides: object):
        value: dict[str, object] = {"supply_workbooks":[str(self.second), str(self.first)], "sample_max_workbooks":2, "sample_max_rows_per_workbook":2, "batch_size":1, "expected_total_supply_rows":20, "report_label":"synthetic-scale-sample"}
        value.update(overrides); self.config_path.write_text(json.dumps(value), encoding="utf-8")
        return load_scale_preflight_config(self.config_path)

    def test_actual_adapter_stably_bounds_workbooks_and_rows(self) -> None:
        with patch("data_pipeline.ingest.nids_supply_excel.create_source_lineage", side_effect=AssertionError("no full checksum")):
            report = run_scale_preflight(self.config(sample_max_workbooks=1), self.report)
        self.assertEqual(report["sampling"]["selected_workbook_count"], 1)
        self.assertEqual(report["workbooks"][0]["rows_read"], 2)
        self.assertEqual(report["workbooks"][0]["rows_emitted"], 2)

    def test_canonical_report_eta_and_rejection_accounting(self) -> None:
        report = run_scale_preflight(self.config(), self.report)
        self.assertEqual(self.report.read_bytes(), json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
        self.assertEqual(report["workbooks"][1]["rows_rejected"], 1)
        self.assertEqual(report["eta"]["expected_total_supply_rows"], 20)
        self.assertAlmostEqual(report["eta"]["estimated_seconds"], round(20 / report["measurement"]["emitted_rows_per_second"], 6), places=6)

    def test_null_eta_and_fail_closed_cases(self) -> None:
        self.assertIsNone(run_scale_preflight(self.config(expected_total_supply_rows=None), self.report)["eta"])
        with self.assertRaises(ScalePreflightConfigError): self.config(supply_workbooks=[])
        with self.assertRaises(ScalePreflightConfigError): self.config(batch_size=0)
        empty = self.temp / "empty.xlsx"; workbook(empty, [])
        with self.assertRaises(ScalePreflightError): run_scale_preflight(self.config(supply_workbooks=[str(empty)]), self.report)
        with patch("data_pipeline.observability.scale_preflight.time.perf_counter", return_value=1.0):
            with self.assertRaises(ScalePreflightError): run_scale_preflight(self.config(sample_max_workbooks=1), self.report)

    def test_report_safety_and_atomic_cleanup(self) -> None:
        run_scale_preflight(self.config(), self.report); text = self.report.read_text(encoding="utf-8")
        for forbidden in (str(self.temp), getpass.getuser(), "SYNTHETIC-SUPPLIER-SECRET", "SYNTHETIC-ITEM-SECRET", "synthetic-secret-1"):
            self.assertNotIn(forbidden, text)
        with self.assertRaises(ScalePreflightError): run_scale_preflight(self.config(), ROOT / "report.json")
        target = self.report.parent / "atomic.json"
        with patch("data_pipeline.observability.scale_preflight.os.replace", side_effect=OSError("fail")):
            with self.assertRaises(OSError): atomic_write_canonical_json(target, {"ok": True})
        self.assertFalse(list(self.report.parent.glob(".atomic.json.tmp-*.json")))

    def test_cli(self) -> None:
        self.config(sample_max_workbooks=1)
        result = subprocess.run([sys.executable, "-m", "data_pipeline.observability.scale_preflight", "--config", str(self.config_path), "--report", str(self.report)], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr); self.assertTrue(self.report.is_file())
