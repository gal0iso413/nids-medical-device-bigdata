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

    def _workbook(
        self,
        *,
        name: str = "공급내역보고자료(20260101~20260110).xlsx",
        supplier: str = "알파의료",
        serial: str = "300",
    ) -> Path:
        headers = ["공급자", "공급받은자", *HEADERS]
        values = dict(zip(HEADERS, row(**{"공급내역일련번호": serial})))
        values["공급자"] = supplier
        values["공급받은자"] = "베타병원"
        path = self.root / name
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
        other = self._workbook(supplier="다른상호", serial="999")
        with self.assertRaises(CompanyDisplayNameConflictError):
            build_company_display_name_directory(
                supply_paths=[other],
                output_root=self.root / "facts",
            )

    def test_later_month_keeps_earlier_logical_month_name(self) -> None:
        facts = self.root / "facts"
        build_company_display_name_directory(
            supply_paths=[self._workbook(supplier="알파의료")],
            output_root=facts,
        )
        february = self._workbook(
            name="공급내역보고자료(20260201~20260210).xlsx",
            supplier="다른상호",
            serial="400",
        )
        result = build_company_display_name_directory(supply_paths=[february], output_root=facts)
        self.assertEqual(result.status, "written")
        _manifest, frame = read_company_display_name_directory(facts)
        supplier_row = frame.loc[frame["display_name"].eq("알파의료")]
        self.assertEqual(len(supplier_row), 1)
        self.assertTrue(bool(supplier_row.iloc[0]["name_conflict"]))

    def test_third_month_keeps_existing_month_partition_bytes(self) -> None:
        facts = self.root / "facts"
        build_company_display_name_directory(
            supply_paths=[self._workbook(supplier="알파의료")],
            output_root=facts,
        )
        build_company_display_name_directory(
            supply_paths=[
                self._workbook(
                    name="공급내역보고자료(20260201~20260210).xlsx",
                    supplier="다른상호",
                    serial="400",
                )
            ],
            output_root=facts,
        )
        march = self._workbook(
            name="공급내역보고자료(20260301~20260310).xlsx",
            supplier="세번째상호",
            serial="500",
        )
        result = build_company_display_name_directory(supply_paths=[march], output_root=facts)
        self.assertEqual(result.status, "written")
        manifest, frame = read_company_display_name_directory(facts)
        self.assertEqual(
            [entry["month"] for entry in manifest["source_months"]],
            ["202601", "202602", "202603"],
        )
        self.assertIn("알파의료", set(frame["display_name"]))
