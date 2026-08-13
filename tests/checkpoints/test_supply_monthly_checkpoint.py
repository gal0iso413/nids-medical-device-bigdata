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
from pandas.testing import assert_frame_equal

import data_pipeline.checkpoints.supply_monthly as checkpoint_module

from data_pipeline.aggregates import aggregate_company_counterparty_product_month
from data_pipeline.checkpoints import (
    AllRowsUnmatchedError,
    CheckpointIntegrityError,
    CheckpointLineageError,
    CheckpointMemoryLimitError,
    CheckpointSealedError,
    EmptySupplyInputError,
    IncompleteSourcePassError,
    SealedManifestConflictError,
    SourceRowConflictError,
    create_or_open_supply_monthly_checkpoint,
    finalize_sealed_supply_checkpoint,
    read_sealed_month_fact,
    verify_sealed_supply_checkpoint,
)
from data_pipeline.contracts import ContractValidationError
from data_pipeline.ingest import (
    ADAPTER_CONTRACT_VERSION,
    SOURCE_BATCH_COLUMNS,
    SheetIngestionProfile,
    SourceLineage,
    SupplyIngestionReport,
    WorkbookSnapshot,
)
from data_pipeline.storage import MasterLookupVerification


TEMP_PARENT = Path(tempfile.gettempdir())


def source_id(number: int) -> str:
    return f"nids-row-v1:{number:064x}"


def source_row(
    number: int,
    *,
    month: str = "202601",
    item: int = 10,
    matched_group: str | None = "GROUP-A",
    item_name: str | None = "ITEM-A",
    udi: str | None = None,
    day: int = 5,
    transaction_type: str = "SUPPLY",
    amount: str | None = "1000.25",
    raw_qty: str | None = "2",
    piece_qty: str | None = None,
    flags: str = "",
) -> dict[str, object]:
    return {
        "supply_date": f"{month[:4]}-{month[4:]}-{day:02d}",
        "src_company_id": "co:100",
        "dst_company_id": "co:200",
        "item_serial": item,
        "model_serial": item + 10,
        "udi_serial": item + 20,
        "item_group_id": matched_group,
        "item_name_id": item_name,
        "transaction_type": transaction_type,
        "amount_clean": amount,
        "raw_supply_qty": raw_qty,
        "piece_qty": piece_qty,
        "udi": udi,
        "supplier_type": "manufacturer",
        "receiver_type": "distributor",
        "supplier_region": "11",
        "receiver_region": "26",
        "source_version": "nids-supply-v1:" + "a" * 64,
        "source_row_id": source_id(number),
        "row_quality_flags": flags,
    }


def frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=SOURCE_BATCH_COLUMNS)


def lineage() -> SourceLineage:
    return SourceLineage(
        ADAPTER_CONTRACT_VERSION,
        "nids-supply-v1:" + "a" * 64,
        (WorkbookSnapshot("synthetic-supply.xlsx", 123, "b" * 64),),
    )


def master() -> MasterLookupVerification:
    return MasterLookupVerification(
        "nids-master-v1:" + "c" * 64,
        "c" * 64,
        "master_product_lookup/schema_version=1.0.0/source_hash=" + "c" * 64 + "/master_keys.sqlite",
        "d" * 64,
        456,
        100,
    )


def report(rows: int) -> SupplyIngestionReport:
    value = SupplyIngestionReport()
    value.sheet_profiles.append(
        SheetIngestionProfile(
            workbook="synthetic-supply.xlsx",
            sheet="data",
            rows_read=rows,
            rows_emitted=rows,
        )
    )
    return value


def sample_rows() -> list[dict[str, object]]:
    return [
        source_row(1, udi="UDI-A", day=5, flags="high_value_review"),
        source_row(2, udi="UDI-B", day=7, amount=None, item_name="ITEM-B"),
        source_row(3, month="202602", item=40, udi="UDI-C", piece_qty="3"),
        source_row(4, month="202602", item=90, udi="UDI-X"),
    ]


def write_canonical(path: Path, value: dict[str, object]) -> None:
    path.write_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


class SupplyMonthlyCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TEMP_PARENT / f".supply-checkpoint-{uuid4().hex[:10]}"
        self.temp_dir.mkdir(parents=True)
        self.root = self.temp_dir / "checkpoint"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def open(self, root: Path | None = None):
        return create_or_open_supply_monthly_checkpoint(
            root or self.root,
            supply_lineage=lineage(),
            master_verification=master(),
        )

    def test_two_batch_two_month_reduce_equals_one_shot_pr01(self) -> None:
        rows = sample_rows()
        with self.open() as checkpoint:
            first = checkpoint.apply_classified_batch(
                frame([rows[0], rows[3]]), matched_mask=[True, False]
            )
            second = checkpoint.apply_classified_batch(
                frame([rows[1], rows[2]]), matched_mask=[True, True]
            )
            self.assertEqual((first.matched_new, first.unmatched_new), (1, 1))
            self.assertEqual((second.matched_new, second.unmatched_new), (2, 0))
            sealed = checkpoint.seal(adapter_report=report(4), max_fact_bytes=1_000_000)
        self.assertEqual((sealed.ledger_rows, sealed.matched_rows, sealed.unmatched_rows), (4, 3, 1))
        actual = pd.concat(
            [
                read_sealed_month_fact(self.root, sealed.run_id, month, max_fact_bytes=1_000_000)
                for month in sealed.months
            ],
            ignore_index=True,
        )
        expected = aggregate_company_counterparty_product_month(frame(rows[:3]))
        assert_frame_equal(actual, expected)

    def test_all_normal_rows_are_classified_and_unmatched_do_not_accumulate(self) -> None:
        rows = sample_rows()
        with self.open() as checkpoint:
            result = checkpoint.apply_classified_batch(
                frame(rows), matched_mask=[True, False, True, False]
            )
            self.assertEqual((result.rows_new, result.matched_new, result.unmatched_new), (4, 2, 2))
            counts = checkpoint._connection.execute(
                "SELECT classification,COUNT(*) FROM source_row_ledger GROUP BY classification ORDER BY classification"
            ).fetchall()
            self.assertEqual([tuple(row) for row in counts], [(0, 2), (1, 2)])
            tx_count = checkpoint._connection.execute(
                "SELECT SUM(tx_count) FROM grain_accumulator"
            ).fetchone()[0]
            self.assertEqual(tx_count, 2)

    def test_identical_replay_is_noop_for_ledger_and_accumulator(self) -> None:
        batch = frame(sample_rows()[:3])
        with self.open() as checkpoint:
            first = checkpoint.apply_classified_batch(batch, matched_mask=[True, True, False])
            second = checkpoint.apply_classified_batch(batch, matched_mask=[True, True, False])
            self.assertEqual(first.rows_new, 3)
            self.assertEqual((second.rows_new, second.rows_replayed), (0, 3))
            self.assertEqual(
                checkpoint._connection.execute("SELECT SUM(tx_count) FROM grain_accumulator").fetchone()[0],
                2,
            )

    def test_exact_duplicate_inside_batch_is_counted_as_replay_once(self) -> None:
        row = source_row(1)
        with self.open() as checkpoint:
            result = checkpoint.apply_classified_batch(
                frame([row, row.copy()]), matched_mask=[True, True]
            )
            self.assertEqual((result.rows_input, result.rows_new, result.rows_replayed), (2, 1, 1))
            self.assertEqual(
                checkpoint._connection.execute("SELECT SUM(tx_count) FROM grain_accumulator").fetchone()[0],
                1,
            )

    def test_batch_boundaries_do_not_change_fact_or_fingerprint(self) -> None:
        rows = sample_rows()
        root_two = self.temp_dir / "checkpoint-two"
        with self.open() as one:
            one.apply_classified_batch(frame(rows), matched_mask=[True, True, True, False])
            sealed_one = one.seal(adapter_report=report(4), max_fact_bytes=1_000_000)
        with self.open(root_two) as two:
            two.apply_classified_batch(frame(rows[:1]), matched_mask=[True])
            two.apply_classified_batch(frame(rows[1:]), matched_mask=[True, True, False])
            sealed_two = two.seal(adapter_report=report(4), max_fact_bytes=1_000_000)
        self.assertEqual(sealed_one.fact_fingerprints, sealed_two.fact_fingerprints)
        for month in sealed_one.months:
            assert_frame_equal(
                read_sealed_month_fact(self.root, sealed_one.run_id, month, max_fact_bytes=1_000_000),
                read_sealed_month_fact(root_two, sealed_two.run_id, month, max_fact_bytes=1_000_000),
            )

    def test_same_id_different_content_rolls_back_whole_batch(self) -> None:
        original = source_row(1)
        changed = source_row(1, amount="999")
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame([original]), matched_mask=[True])
            with self.assertRaises(SourceRowConflictError):
                checkpoint.apply_classified_batch(
                    frame([source_row(2), changed]), matched_mask=[True, True]
                )
            ids = checkpoint._connection.execute(
                "SELECT source_row_digest FROM source_row_ledger"
            ).fetchall()
            self.assertEqual(len(ids), 1)
            self.assertEqual(checkpoint._connection.execute("SELECT SUM(tx_count) FROM grain_accumulator").fetchone()[0], 1)
            retry = checkpoint.apply_classified_batch(
                frame([source_row(2)]), matched_mask=[True]
            )
            self.assertEqual(retry.rows_new, 1)

    def test_same_id_different_classification_is_conflict(self) -> None:
        batch = frame([source_row(1)])
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(batch, matched_mask=[True])
            with self.assertRaises(SourceRowConflictError):
                checkpoint.apply_classified_batch(batch, matched_mask=[False])

    def test_decimal_null_distinct_dimension_and_flags_equal_one_shot(self) -> None:
        rows = sample_rows()[:3]
        with self.open() as checkpoint:
            for row in rows:
                checkpoint.apply_classified_batch(frame([row]), matched_mask=[True])
            sealed = checkpoint.seal(adapter_report=report(3), max_fact_bytes=1_000_000)
        actual = pd.concat(
            [read_sealed_month_fact(self.root, sealed.run_id, m, max_fact_bytes=1_000_000) for m in sealed.months],
            ignore_index=True,
        )
        expected = aggregate_company_counterparty_product_month(frame(rows))
        assert_frame_equal(actual, expected)
        january = actual.loc[actual["month"].eq("202601")].iloc[0]
        self.assertEqual(january["amount_sum_clean"], Decimal("1000.25"))
        self.assertEqual(january["unique_udi_count"], 2)
        self.assertEqual(january["active_day_count"], 2)
        self.assertIn("item_name_id_conflict", january["quality_flags"])
        self.assertIn("high_value_review", january["quality_flags"])

    def test_return_recall_unknown_and_negative_block_entire_batch(self) -> None:
        cases = [
            (source_row(1, transaction_type="RETURN"), "transaction_sign_policy_pending"),
            (source_row(1, transaction_type="RECALL"), "transaction_sign_policy_pending"),
            (source_row(1, transaction_type="DISCARD"), "transaction_type_unknown"),
            (source_row(1, transaction_type="LEASE"), "transaction_type_unknown"),
            (source_row(1, amount="-1"), "negative_forward_value"),
        ]
        for position, (row, status) in enumerate(cases):
            root = self.temp_dir / f"c{position}"
            with self.open(root) as checkpoint:
                with self.assertRaisesRegex(ContractValidationError, status):
                    checkpoint.apply_classified_batch(frame([row]), matched_mask=[True])
                self.assertEqual(
                    checkpoint._connection.execute("SELECT COUNT(*) FROM source_row_ledger").fetchone()[0],
                    0,
                )

    def test_empty_and_all_unmatched_cannot_seal(self) -> None:
        with self.open() as checkpoint:
            with self.assertRaises(EmptySupplyInputError):
                checkpoint.seal(adapter_report=report(0), max_fact_bytes=1_000_000)
        root_two = self.temp_dir / "unmatched"
        with self.open(root_two) as checkpoint:
            checkpoint.apply_classified_batch(frame([source_row(1)]), matched_mask=[False])
            with self.assertRaises(AllRowsUnmatchedError):
                checkpoint.seal(adapter_report=report(1), max_fact_bytes=1_000_000)

    def test_seal_requires_eof_report_accounting(self) -> None:
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame([source_row(1)]), matched_mask=[True])
            invalid = report(1)
            invalid.sheet_profiles[0].rows_read = 2
            with self.assertRaisesRegex(Exception, "accounting"):
                checkpoint.seal(adapter_report=invalid, max_fact_bytes=1_000_000)

    def test_sealed_checkpoint_is_immutable_and_has_no_sidecar(self) -> None:
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame([source_row(1)]), matched_mask=[True])
            sealed = checkpoint.seal(adapter_report=report(1), max_fact_bytes=1_000_000)
        database = self.root / sealed.relative_database_path
        self.assertTrue(database.is_file())
        for suffix in ("-wal", "-shm", "-journal"):
            self.assertFalse(Path(str(database) + suffix).exists())
        verify_sealed_supply_checkpoint(self.root, sealed.run_id)
        with self.assertRaises(CheckpointSealedError):
            self.open()

    def test_sealed_database_tampering_is_detected(self) -> None:
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame([source_row(1)]), matched_mask=[True])
            sealed = checkpoint.seal(adapter_report=report(1), max_fact_bytes=1_000_000)
        database = self.root / sealed.relative_database_path
        with database.open("ab") as stream:
            stream.write(b"tamper")
        with self.assertRaises(CheckpointIntegrityError):
            verify_sealed_supply_checkpoint(self.root, sealed.run_id)

    def test_month_reader_checks_conservative_memory_limit(self) -> None:
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame([source_row(1)]), matched_mask=[True])
            sealed = checkpoint.seal(adapter_report=report(1), max_fact_bytes=1_000_000)
        with self.assertRaises(CheckpointMemoryLimitError):
            read_sealed_month_fact(self.root, sealed.run_id, "202601", max_fact_bytes=4095)
        fact = read_sealed_month_fact(
            self.root, sealed.run_id, "202601", max_fact_bytes=4096
        )
        self.assertEqual(len(fact), 1)

    def test_source_row_digest_is_blob_and_prefix_is_not_repeated(self) -> None:
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame([source_row(1)]), matched_mask=[False])
            row = checkpoint._connection.execute(
                "SELECT source_row_digest,typeof(source_row_digest) FROM source_row_ledger"
            ).fetchone()
            self.assertEqual((len(row[0]), row[1]), (32, "blob"))
            columns = checkpoint._connection.execute(
                "PRAGMA table_info(source_row_ledger)"
            ).fetchall()
            self.assertNotIn("source_version", [column[1] for column in columns])

    def test_run_manifest_is_canonical_and_contains_both_lineages(self) -> None:
        with self.open() as checkpoint:
            manifest_path = checkpoint.run_dir / "_run_manifest.json"
            raw = manifest_path.read_bytes()
            manifest = json.loads(raw)
            self.assertEqual(raw, json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
            self.assertEqual(manifest["supply"]["source_version"], lineage().source_version)
            self.assertEqual(manifest["master"]["source_hash"], master().source_hash)

    def test_tampered_run_lineage_is_blocked(self) -> None:
        checkpoint = self.open()
        manifest_path = checkpoint.run_dir / "_run_manifest.json"
        checkpoint.close()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["supply"]["source_version"] = "nids-supply-v1:" + "f" * 64
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        with self.assertRaises(Exception):
            self.open()

    def test_seal_requires_complete_open_session_source_pass(self) -> None:
        rows = sample_rows()[:2]
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame(rows[:1]), matched_mask=[True])
            with self.assertRaises(IncompleteSourcePassError):
                checkpoint.seal(
                    adapter_report=report(2), max_fact_bytes=1_000_000
                )
            self.assertEqual(checkpoint.state, "active")

    def test_reopened_partial_checkpoint_seals_after_full_replay(self) -> None:
        rows = sample_rows()[:2]
        checkpoint = self.open()
        checkpoint.apply_classified_batch(frame(rows[:1]), matched_mask=[True])
        checkpoint.close()
        with self.open() as reopened:
            result = reopened.apply_classified_batch(
                frame(rows), matched_mask=[True, True]
            )
            self.assertEqual((result.rows_new, result.rows_replayed), (1, 1))
            sealed = reopened.seal(
                adapter_report=report(2), max_fact_bytes=1_000_000
            )
        self.assertEqual((sealed.ledger_rows, sealed.matched_rows), (2, 2))

    def test_rolled_back_batch_does_not_increase_session_coverage(self) -> None:
        first = source_row(1)
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame([first]), matched_mask=[True])
            with self.assertRaises(SourceRowConflictError):
                checkpoint.apply_classified_batch(
                    frame([source_row(2), source_row(1, amount="999")]),
                    matched_mask=[True, True],
                )
            with self.assertRaises(IncompleteSourcePassError):
                checkpoint.seal(
                    adapter_report=report(2), max_fact_bytes=1_000_000
                )
            checkpoint.apply_classified_batch(
                frame([source_row(2)]), matched_mask=[True]
            )
            sealed = checkpoint.seal(
                adapter_report=report(2), max_fact_bytes=1_000_000
            )
        self.assertEqual(sealed.ledger_rows, 2)

    def test_physical_exact_duplicate_counts_toward_complete_pass(self) -> None:
        row = source_row(1)
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(
                frame([row, row.copy()]), matched_mask=[True, True]
            )
            sealed = checkpoint.seal(
                adapter_report=report(2), max_fact_bytes=1_000_000
            )
        manifest = json.loads(
            (
                self.root
                / sealed.relative_database_path
            ).parent.joinpath("_sealed_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["sealed_summary"]["quality_report"]["exact_duplicate_rows"],
            1,
        )

    def test_seal_memory_limit_keeps_active_state_and_can_retry(self) -> None:
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(
                frame([source_row(1)]), matched_mask=[True]
            )
            with self.assertRaises(CheckpointMemoryLimitError):
                checkpoint.seal(adapter_report=report(1), max_fact_bytes=4095)
            self.assertEqual(checkpoint.state, "active")
            self.assertEqual(
                checkpoint._connection.execute(
                    "SELECT COUNT(*) FROM sealed_summary"
                ).fetchone()[0],
                0,
            )
            self.assertFalse(
                checkpoint.run_dir.joinpath("_sealed_manifest.json").exists()
            )
            sealed = checkpoint.seal(
                adapter_report=report(1), max_fact_bytes=4096
            )
        self.assertEqual(sealed.months, ("202601",))

    def test_manifest_write_failure_is_recoverable_without_source_replay(self) -> None:
        checkpoint = self.open()
        checkpoint.apply_classified_batch(frame([source_row(1)]), matched_mask=[True])
        original_write = checkpoint_module._write_canonical

        def fail_sealed_manifest(path: Path, value: dict[str, object]) -> None:
            if path.name == "_sealed_manifest.json":
                raise CheckpointIntegrityError("synthetic manifest failure")
            original_write(path, value)

        with patch.object(
            checkpoint_module, "_write_canonical", side_effect=fail_sealed_manifest
        ):
            with self.assertRaisesRegex(CheckpointIntegrityError, "synthetic"):
                checkpoint.seal(
                    adapter_report=report(1), max_fact_bytes=1_000_000
                )
        self.assertFalse(checkpoint.run_dir.joinpath("_sealed_manifest.json").exists())
        recovered = finalize_sealed_supply_checkpoint(self.root, checkpoint.run_id)
        repeated = finalize_sealed_supply_checkpoint(self.root, checkpoint.run_id)
        self.assertEqual(recovered, repeated)
        self.assertEqual(recovered.ledger_rows, 1)

    def test_finalize_rejects_conflicting_existing_manifest(self) -> None:
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame([source_row(1)]), matched_mask=[True])
            sealed = checkpoint.seal(
                adapter_report=report(1), max_fact_bytes=1_000_000
            )
        manifest_path = (self.root / sealed.relative_database_path).parent / "_sealed_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["database_file_size"] += 1
        write_canonical(manifest_path, manifest)
        with self.assertRaises(SealedManifestConflictError):
            finalize_sealed_supply_checkpoint(self.root, sealed.run_id)

    def test_verifier_rejects_manifest_summary_tampering(self) -> None:
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame([source_row(1)]), matched_mask=[True])
            sealed = checkpoint.seal(
                adapter_report=report(1), max_fact_bytes=1_000_000
            )
        manifest_path = (self.root / sealed.relative_database_path).parent / "_sealed_manifest.json"
        original = json.loads(manifest_path.read_text(encoding="utf-8"))
        mutations = (
            lambda value: value["sealed_summary"].__setitem__("ledger_rows", 2),
            lambda value: value["sealed_summary"]["months"][0].__setitem__("grain_count", 2),
            lambda value: value["sealed_summary"]["adapter_report"]["sheet_profiles"][0].__setitem__("rows_read", 2),
        )
        for mutate in mutations:
            tampered = json.loads(json.dumps(original))
            mutate(tampered)
            summary = tampered["sealed_summary"]
            adapter = summary["adapter_report"]
            summary["adapter_report_sha256"] = checkpoint_module._sha256_bytes(
                checkpoint_module._canonical_json_bytes(adapter)
            )
            tampered["sealed_summary_sha256"] = checkpoint_module._sha256_bytes(
                checkpoint_module._canonical_json_bytes(summary)
            )
            write_canonical(manifest_path, tampered)
            with self.assertRaises(CheckpointIntegrityError):
                verify_sealed_supply_checkpoint(self.root, sealed.run_id)
        write_canonical(manifest_path, original)
        verify_sealed_supply_checkpoint(self.root, sealed.run_id)

    def test_verifier_rejects_run_payload_with_recomputed_run_id(self) -> None:
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(frame([source_row(1)]), matched_mask=[True])
            sealed = checkpoint.seal(
                adapter_report=report(1), max_fact_bytes=1_000_000
            )
        run_path = (self.root / sealed.relative_database_path).parent / "_run_manifest.json"
        run_manifest = json.loads(run_path.read_text(encoding="utf-8"))
        run_manifest["supply"]["source_version"] = "nids-supply-v1:" + "f" * 64
        payload = {key: value for key, value in run_manifest.items() if key != "run_id"}
        run_manifest["run_id"] = checkpoint_module._sha256_bytes(
            checkpoint_module._canonical_json_bytes(payload)
        )
        write_canonical(run_path, run_manifest)
        with self.assertRaises(CheckpointLineageError):
            verify_sealed_supply_checkpoint(self.root, sealed.run_id)

    def test_run_manifest_only_initialization_can_retry(self) -> None:
        checkpoint = self.open()
        run_dir = checkpoint.run_dir
        checkpoint.close()
        database = run_dir / "checkpoint.sqlite"
        database.unlink()
        with self.open() as recovered:
            self.assertEqual(recovered.state, "active")
            recovered.apply_classified_batch(
                frame([source_row(1)]), matched_mask=[True]
            )

    def test_existing_malformed_database_is_not_replaced(self) -> None:
        checkpoint = self.open()
        database = checkpoint.run_dir / "checkpoint.sqlite"
        checkpoint.close()
        original = b"not-a-sqlite-database"
        database.write_bytes(original)
        with self.assertRaises(Exception):
            self.open()
        self.assertEqual(database.read_bytes(), original)

    def test_sealed_quality_report_has_bounded_unmatched_ids(self) -> None:
        rows = [source_row(1)] + [source_row(number) for number in range(2, 27)]
        with self.open() as checkpoint:
            checkpoint.apply_classified_batch(
                frame(rows), matched_mask=[True] + [False] * 25
            )
            sealed = checkpoint.seal(adapter_report=report(26), max_fact_bytes=1_000_000)
        sealed_path = self.root / sealed.relative_database_path
        manifest = json.loads(
            (sealed_path.parent / "_sealed_manifest.json").read_text(encoding="utf-8")
        )
        quality = manifest["sealed_summary"]["quality_report"]
        self.assertEqual(len(quality["unmatched_source_row_ids"]), 20)
        self.assertEqual(quality["unmatched_omitted"], 5)


if __name__ == "__main__":
    unittest.main()
