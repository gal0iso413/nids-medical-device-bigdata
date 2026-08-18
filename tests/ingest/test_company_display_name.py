from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest
from uuid import uuid4

from data_pipeline.ingest.company_display_name import (
    CompanyDisplayNameConflictError,
    build_company_display_name_directory,
    read_company_display_name_directory,
)
from .test_nids_supply_excel import HEADERS, row, write_workbook


class CompanyDisplayNameDirectoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.gettempdir()) / f"company-display-name-{uuid4().hex}"
        self.root.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _workbook(self) -> Path:
        headers = ["공급자", "공급받은자", *HEADERS]
        values = dict(zip(HEADERS, row()))
        values["공급자"] = "알파의료"
        values["공급받은자"] = "베타병원"
        path = self.root / "supply.xlsx"
        write_workbook(
            path,
            sheets=[("data", [headers, [values.get(header) for header in headers]])],
        )
        return path

    def test_catch_up_builder_writes_names_without_fact_columns(self) -> None:
        result = build_company_display_name_directory(
            supply_paths=[self._workbook()],
            output_root=self.root / "facts",
        )
        self.assertEqual(result.status, "written")
        self.assertEqual(result.entity_count, 2)
        loaded = read_company_display_name_directory(self.root / "facts")
        self.assertIsNotNone(loaded)
        manifest, frame = loaded
        self.assertTrue(manifest["names_are_not_identifiers"])
        self.assertEqual(set(frame["display_name"]), {"알파의료", "베타병원"})
        unchanged = build_company_display_name_directory(
            supply_paths=[self._workbook()],
            output_root=self.root / "facts",
        )
        self.assertEqual(unchanged.status, "unchanged")

    def test_different_content_is_a_conflict(self) -> None:
        build_company_display_name_directory(
            supply_paths=[self._workbook()],
            output_root=self.root / "facts",
        )
        headers = ["공급자", "공급받은자", *HEADERS]
        values = dict(zip(HEADERS, row(**{"공급내역일련번호": "999"})))
        values["공급자"] = "다른상호"
        values["공급받은자"] = "베타병원"
        other = self.root / "other.xlsx"
        write_workbook(
            other,
            sheets=[("data", [headers, [values.get(header) for header in headers]])],
        )
        with self.assertRaises(CompanyDisplayNameConflictError):
            build_company_display_name_directory(
                supply_paths=[other],
                output_root=self.root / "facts",
            )
