from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import pandas as pd
from openpyxl import Workbook

import data_pipeline.orchestration.supply_monthly as orchestration
from data_pipeline.checkpoints import (
    SupplyMonthlyCheckpoint,
    derive_supply_monthly_run_id,
)
from data_pipeline.ingest import create_source_lineage
from data_pipeline.ingest.company_display_name import read_company_display_name_directory
from data_pipeline.orchestration import (
    CompleteManifestConflictError,
    SupplyMonthlyOrchestrationError,
    UnsafeOrchestrationPathError,
    run_supply_monthly_orchestration,
)
from data_pipeline.storage import (
    PartitionIntegrityError,
    build_master_product_lookup,
    read_monthly_fact_partitions,
    verify_master_product_lookup,
)


SUPPLY_HEADERS = [
    "공급일자",
    "공급한자 업체일련번호",
    "공급자",
    "공급받은자 업체일련번호",
    "공급받은자",
    "요양기관기호(의료기관)",
    "의료기기품목일련번호",
    "모델일련번호",
    "UDI-DI 일련번호",
    "품목군",
    "품목명",
    "공급구분",
    "공급금액",
    "공급수량",
    "포장내 총 수량",
    "낱개총수량",
    "UDI-DI",
    "업종",
    "공급받은자업종",
    "공급한자의 소재지 시도코드",
    "공급받은자의 소재지 시도코드",
    "거래처 코드",
    "공급내역기준연월",
    "공급내역작업일련번호",
    "공급내역일련번호",
    "공급내역보고자료복합Key",
]
MASTER_HEADERS = ["의료기기품목일련번호", "모델일련번호", "UDIDI일련번호"]


def supply_row(
    number: int,
    *,
    month: str,
    item: int,
    model: int,
    udi_serial: int,
    transaction_type: str = "출고",
) -> list[object]:
    values: dict[str, object] = {
        "공급일자": f"{month}15",
        "공급한자 업체일련번호": "10",
        "공급자": "합성공급사",
        "공급받은자 업체일련번호": "20",
        "공급받은자": "합성수령사",
        "요양기관기호(의료기관)": None,
        "의료기기품목일련번호": item,
        "모델일련번호": model,
        "UDI-DI 일련번호": udi_serial,
        "품목군": f"SYNTHETIC-GROUP-{item}",
        "품목명": f"SYNTHETIC-ITEM-{item}",
        "공급구분": transaction_type,
        "공급금액": "1000.250000",
        "공급수량": "2",
        "포장내 총 수량": "5",
        "낱개총수량": "10",
        "UDI-DI": f"SYNTHETIC-UDI-{udi_serial}",
        "업종": "SYNTHETIC-SUPPLIER",
        "공급받은자업종": "SYNTHETIC-RECEIVER",
        "공급한자의 소재지 시도코드": "01",
        "공급받은자의 소재지 시도코드": "02",
        "거래처 코드": "100",
        "공급내역기준연월": month,
        "공급내역작업일련번호": str(2000 + number),
        "공급내역일련번호": str(3000 + number),
        "공급내역보고자료복합Key": f"synthetic-{number}",
    }
    return [values[header] for header in SUPPLY_HEADERS]


def write_workbook(path: Path, sheets: list[tuple[str, list[list[object]]]]) -> None:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets:
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    workbook.save(path)
    workbook.close()


class SupplyMonthlyOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.gettempdir()) / f".supply-orchestration-{uuid4().hex[:10]}"
        self.temp_dir.mkdir(parents=True)
        self.supply = self.temp_dir / "공급내역보고자료(20260101~20260110).xlsx"
        self.master = self.temp_dir / "synthetic-master.xlsx"
        self.master_root = self.temp_dir / "master-lookup"
        self.checkpoint_root = self.temp_dir / "checkpoint"
        self.output_root = self.temp_dir / "service-data"
        write_workbook(
            self.master,
            [("data", [MASTER_HEADERS, [1, 2, 3], [4, 5, 6]])],
        )
        built = build_master_product_lookup([self.master], self.master_root)
        self.master_source_hash = built.source_hash

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def write_supply(self, rows: list[list[object]]) -> None:
        write_workbook(self.supply, [("data", [SUPPLY_HEADERS, *rows])])

    def run_pipeline(self, *, batch_size: int = 2, supply_path: Path | None = None):
        return run_supply_monthly_orchestration(
            supply_paths=[supply_path or self.supply],
            master_lookup_root=self.master_root,
            master_source_hash=self.master_source_hash,
            checkpoint_root=self.checkpoint_root,
            output_root=self.output_root,
            max_month_fact_bytes=10_000_000,
            batch_size=batch_size,
        )

    def complete_path(self, result) -> Path:
        return self.checkpoint_root.joinpath(
            *Path(result.relative_complete_manifest_path).parts
        )

    def test_end_to_end_exact_keys_and_unmatched_rows_stay_in_declared_month(self) -> None:
        self.write_supply(
            [
                supply_row(1, month="202601", item=1, model=2, udi_serial=3),
                # Same UDI serial, different other two keys: exact join must not match.
                supply_row(2, month="202601", item=9, model=8, udi_serial=3),
            ]
        )
        result = self.run_pipeline(batch_size=2)
        self.assertEqual(
            result.run_id,
            derive_supply_monthly_run_id(
                create_source_lineage([self.supply]),
                verify_master_product_lookup(
                    self.master_root, self.master_source_hash
                ),
            ),
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.written_months, ("202601",))
        self.assertEqual(result.skipped_unmatched_only_months, ())
        fact = read_monthly_fact_partitions(self.output_root)
        self.assertEqual(fact["month"].tolist(), ["202601"])
        self.assertEqual(fact["tx_count"].tolist(), [1])
        raw_manifest = self.complete_path(result).read_bytes()
        manifest = json.loads(raw_manifest.decode("utf-8"))
        self.assertEqual(
            raw_manifest,
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8"),
        )
        fingerprint = manifest.pop("complete_payload_fingerprint")
        self.assertEqual(
            fingerprint,
            orchestration.sha256(
                orchestration._canonical_json_bytes(manifest)
            ).hexdigest(),
        )
        manifest["complete_payload_fingerprint"] = fingerprint
        self.assertEqual(
            [entry["month"] for entry in manifest["published_months"]],
            ["202601"],
        )
        self.assertNotIn(str(self.temp_dir), self.complete_path(result).read_text(encoding="utf-8"))
        loaded = read_company_display_name_directory(self.output_root)
        self.assertIsNotNone(loaded)
        _manifest, names = loaded
        self.assertEqual(set(names["display_name"]), {"합성공급사", "합성수령사"})

    def test_later_month_run_does_not_reprocess_published_january(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        january = self.run_pipeline()
        february = self.temp_dir / "공급내역보고자료(20260201~20260210).xlsx"
        write_workbook(
            february,
            [("data", [SUPPLY_HEADERS, supply_row(3, month="202602", item=4, model=5, udi_serial=6)])],
        )
        second = self.run_pipeline(supply_path=february)
        self.assertNotEqual(january.run_id, second.run_id)
        self.assertEqual(second.written_months, ("202602",))
        fact = read_monthly_fact_partitions(self.output_root)
        self.assertEqual(sorted(fact["month"].tolist()), ["202601", "202602"])

    def test_batches_are_range_indexed_and_mask_matches_join_report(self) -> None:
        self.write_supply(
            [
                supply_row(1, month="202601", item=1, model=2, udi_serial=3),
                supply_row(2, month="202601", item=9, model=8, udi_serial=3),
                supply_row(3, month="202602", item=4, model=5, udi_serial=6),
            ]
        )
        observations: list[tuple[list[int], list[bool]]] = []
        original = SupplyMonthlyCheckpoint.apply_classified_batch

        def inspect(checkpoint, batch: pd.DataFrame, *, matched_mask):
            observations.append((batch.index.tolist(), list(map(bool, matched_mask))))
            return original(checkpoint, batch, matched_mask=matched_mask)

        with patch.object(SupplyMonthlyCheckpoint, "apply_classified_batch", new=inspect):
            self.run_pipeline(batch_size=2)
        self.assertEqual(observations, [([0, 1], [True, False]), ([0], [True])])

    def test_mid_batch_failure_preserves_active_checkpoint_and_full_replay_recovers(self) -> None:
        self.write_supply(
            [
                supply_row(1, month="202601", item=1, model=2, udi_serial=3),
                supply_row(2, month="202602", item=4, model=5, udi_serial=6),
            ]
        )
        original = SupplyMonthlyCheckpoint.apply_classified_batch
        calls = 0

        def fail_second(checkpoint, batch: pd.DataFrame, *, matched_mask):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("synthetic batch failure")
            return original(checkpoint, batch, matched_mask=matched_mask)

        with patch.object(SupplyMonthlyCheckpoint, "apply_classified_batch", new=fail_second):
            with self.assertRaisesRegex(RuntimeError, "synthetic batch failure"):
                self.run_pipeline(batch_size=1)
        self.assertFalse(self.output_root.exists())
        recovered = self.run_pipeline(batch_size=2)
        self.assertEqual(recovered.written_months, ("202601",))

    def test_pre_eof_error_never_calls_parquet_writer(self) -> None:
        self.write_supply(
            [
                supply_row(1, month="202601", item=1, model=2, udi_serial=3),
                supply_row(2, month="202601", item=4, model=5, udi_serial=6),
            ]
        )
        original = SupplyMonthlyCheckpoint.apply_classified_batch
        calls = {"count": 0}

        def fail_second(checkpoint, batch: pd.DataFrame, *, matched_mask):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("synthetic pre-eof failure")
            return original(checkpoint, batch, matched_mask=matched_mask)
        with patch.object(SupplyMonthlyCheckpoint, "apply_classified_batch", new=fail_second):
            with patch.object(orchestration, "write_monthly_fact_partitions") as writer:
                with self.assertRaisesRegex(RuntimeError, "synthetic pre-eof failure"):
                    self.run_pipeline(batch_size=1)
        writer.assert_not_called()

    def test_eof_accounting_failure_never_calls_parquet_writer(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        original_stream = orchestration.stream_nids_supply_excel

        class InvalidAccountingStream:
            def __init__(self, stream):
                self.stream = stream
                self.lineage = stream.lineage
                self.report = stream.report

            def __enter__(self):
                self.stream.__enter__()
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return self.stream.__exit__(exc_type, exc_value, traceback)

            def __iter__(self):
                yield from self.stream
                self.report.sheet_profiles[0].rows_read += 1

        def invalid_stream(paths, *, batch_size):
            return InvalidAccountingStream(
                original_stream(paths, batch_size=batch_size)
            )

        with patch.object(
            orchestration, "stream_nids_supply_excel", side_effect=invalid_stream
        ), patch.object(orchestration, "write_monthly_fact_partitions") as writer:
            with self.assertRaisesRegex(Exception, "accounting"):
                self.run_pipeline()
        writer.assert_not_called()

    def test_sealed_rerun_skips_excel_stream_and_recreates_complete_manifest(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        first = self.run_pipeline()
        self.complete_path(first).unlink()
        with patch.object(
            orchestration,
            "stream_nids_supply_excel",
            side_effect=AssertionError("sealed run must not stream Excel"),
        ):
            second = self.run_pipeline()
        self.assertEqual(second.status, "completed")
        self.assertEqual(second.unchanged_months, ("202601",))

    def test_sealed_database_without_manifest_uses_read_only_finalize_recovery(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        first = self.run_pipeline()
        run_dir = self.complete_path(first).parent
        self.complete_path(first).unlink()
        run_dir.joinpath("_sealed_manifest.json").unlink()
        with patch.object(
            orchestration,
            "stream_nids_supply_excel",
            side_effect=AssertionError("sealed recovery must not stream Excel"),
        ):
            recovered = self.run_pipeline()
        self.assertEqual(recovered.status, "completed")
        self.assertTrue(run_dir.joinpath("_sealed_manifest.json").is_file())

    def test_later_partition_failure_preserves_first_and_rerun_resumes(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        self.run_pipeline()
        february = self.temp_dir / "공급내역보고자료(20260201~20260210).xlsx"
        write_workbook(
            february,
            [("data", [SUPPLY_HEADERS, supply_row(2, month="202602", item=4, model=5, udi_serial=6)])],
        )
        original = orchestration.write_monthly_fact_partitions

        def fail_february(fact, output_root):
            if fact.iloc[0]["month"] == "202602":
                raise RuntimeError("synthetic publication failure")
            return original(fact, output_root)

        with patch.object(
            orchestration, "write_monthly_fact_partitions", side_effect=fail_february
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic publication failure"):
                self.run_pipeline(supply_path=february)
        january = self.output_root / "fact_company_counterparty_product_month" / "schema_version=1.0.0" / "month=202601"
        self.assertTrue(january.is_dir())
        february_complete = [
            path for path in self.checkpoint_root.rglob("_complete_manifest.json")
            if "202602" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(february_complete, [])
        resumed = self.run_pipeline(supply_path=february)
        self.assertEqual(resumed.written_months, ("202602",))
        self.assertEqual(resumed.unchanged_months, ())

    def test_complete_manifest_write_failure_retries_without_republishing(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        with patch.object(
            orchestration,
            "_publish_complete_manifest",
            side_effect=SupplyMonthlyOrchestrationError("synthetic complete failure"),
        ):
            with self.assertRaisesRegex(SupplyMonthlyOrchestrationError, "synthetic"):
                self.run_pipeline()
        self.assertEqual(list(self.checkpoint_root.rglob("_complete_manifest.json")), [])
        resumed = self.run_pipeline()
        self.assertEqual(resumed.unchanged_months, ("202601",))
        self.assertTrue(self.complete_path(resumed).is_file())

    def test_partition_verification_failure_blocks_complete_manifest(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        original = orchestration.verify_monthly_fact_partition

        def fail_january(output_root, month):
            if month == "202601":
                raise PartitionIntegrityError("synthetic verify failure")
            return original(output_root, month)

        with patch.object(
            orchestration,
            "verify_monthly_fact_partition",
            side_effect=fail_january,
        ):
            with self.assertRaisesRegex(PartitionIntegrityError, "synthetic"):
                self.run_pipeline()
        self.assertEqual(list(self.checkpoint_root.rglob("_complete_manifest.json")), [])

    def test_complete_state_revalidates_and_returns_unchanged(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        first = self.run_pipeline()
        second = self.run_pipeline()
        self.assertEqual(second.status, "unchanged")
        self.assertEqual(second.unchanged_months, ("202601",))
        self.assertEqual(self.complete_path(first).read_bytes(), self.complete_path(second).read_bytes())

    def test_corrupt_complete_manifest_is_conflict(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        result = self.run_pipeline()
        self.complete_path(result).write_text("{}", encoding="utf-8")
        with self.assertRaises(CompleteManifestConflictError):
            self.run_pipeline()

    def test_corrupt_parquet_is_blocked_in_complete_state(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        self.run_pipeline()
        parquet = next(self.output_root.rglob("*.parquet"))
        with parquet.open("ab") as stream:
            stream.write(b"tamper")
        with self.assertRaises(PartitionIntegrityError):
            self.run_pipeline()

    def test_corrupt_partition_manifest_is_blocked_in_complete_state(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        self.run_pipeline()
        partition_manifest = next(
            path
            for path in self.output_root.rglob("_manifest.json")
            if "month=202601" in str(path)
        )
        partition_manifest.write_text("{}", encoding="utf-8")
        with self.assertRaises(PartitionIntegrityError):
            self.run_pipeline()

    def test_overlapping_roots_are_rejected_before_artifacts(self) -> None:
        self.write_supply(
            [supply_row(1, month="202601", item=1, model=2, udi_serial=3)]
        )
        cases = (
            (self.temp_dir / "same", self.temp_dir / "same"),
            (self.temp_dir / "parent", self.temp_dir / "parent" / "child"),
            (self.temp_dir / "parent" / "child", self.temp_dir / "parent"),
        )
        for checkpoint_root, output_root in cases:
            with self.assertRaises(UnsafeOrchestrationPathError):
                run_supply_monthly_orchestration(
                    supply_paths=[self.supply],
                    master_lookup_root=self.master_root,
                    master_source_hash=self.master_source_hash,
                    checkpoint_root=checkpoint_root,
                    output_root=output_root,
                    max_month_fact_bytes=1_000_000,
                )
            self.assertFalse(checkpoint_root.exists())
            self.assertFalse(output_root.exists())


if __name__ == "__main__":
    unittest.main()
