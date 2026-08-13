from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from uuid import uuid4

import pandas as pd
from pandas.testing import assert_frame_equal
import pyarrow as pa
import pyarrow.parquet as pq

from data_pipeline.aggregates import aggregate_company_counterparty_product_month
from data_pipeline.contracts import MONTHLY_FACT_COLUMNS, empty_monthly_fact
from data_pipeline.storage.monthly_fact_parquet import (
    ARROW_SCHEMA,
    DATASET_NAME,
    DECIMAL_COLUMNS,
    FACT_SCHEMA_VERSION,
    MANIFEST_FILENAME,
    MonthlyFactStorageError,
    PARQUET_FILENAME,
    DecimalEncodingError,
    InvalidPartitionRequestError,
    PartitionConflictError,
    PartitionIntegrityError,
    read_monthly_fact_partitions,
    verify_monthly_fact_partition,
    write_monthly_fact_partitions,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "supply_monthly_small.txt"
TEST_TEMP_PARENT = REPOSITORY_ROOT.parent


def sample_fact() -> pd.DataFrame:
    rows = pd.DataFrame(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
    return aggregate_company_counterparty_product_month(rows)


def partition_dir(root: Path, month: str) -> Path:
    return (
        root
        / DATASET_NAME
        / f"schema_version={FACT_SCHEMA_VERSION}"
        / f"month={month}"
    )


def manifest(root: Path, month: str) -> dict[str, object]:
    return json.loads(
        (partition_dir(root, month) / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )


class MonthlyFactParquetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TEST_TEMP_PARENT / f".mfp-{uuid4().hex[:8]}"
        self.temp_dir.mkdir(parents=True)
        self.output_root = self.temp_dir / "store"
        self.fact = sample_fact()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_writes_two_months_to_exact_partition_paths(self) -> None:
        result = write_monthly_fact_partitions(self.fact, self.output_root)

        self.assertEqual(result.written_months, ("202601", "202602"))
        self.assertEqual(result.unchanged_months, ())
        self.assertEqual(result.partition_count, 2)
        for month in result.written_months:
            directory = partition_dir(self.output_root, month)
            self.assertTrue((directory / PARQUET_FILENAME).is_file())
            self.assertTrue((directory / MANIFEST_FILENAME).is_file())

    def test_manifest_has_required_fields_and_canonical_json(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        path = partition_dir(self.output_root, "202601") / MANIFEST_FILENAME
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))

        self.assertEqual(
            raw,
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8"),
        )
        self.assertEqual(
            set(value),
            {
                "dataset_name",
                "logical_schema_name",
                "logical_schema_version",
                "logical_schema_fingerprint",
                "storage_contract_version",
                "partition_column",
                "partition_value",
                "relative_parquet_path",
                "row_count",
                "column_order",
                "source_versions",
                "compression",
                "decimal_encoding",
                "parquet_file_size",
                "parquet_sha256",
            },
        )
        self.assertEqual(value["partition_value"], "202601")
        self.assertEqual(value["column_order"], list(MONTHLY_FACT_COLUMNS))
        self.assertEqual(value["source_versions"], ["fixture-v1"])
        self.assertEqual(value["compression"], "zstd")
        self.assertNotIn(str(self.output_root), value["relative_parquet_path"])
        self.assertEqual(
            value["relative_parquet_path"],
            "fact_company_counterparty_product_month/schema_version=1.0.0/"
            "month=202601/part-00000.parquet",
        )

    def test_round_trip_preserves_values_columns_and_dtypes(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        actual = read_monthly_fact_partitions(self.output_root)
        expected = self.fact.sort_values(
            ["month", "src_company_id", "dst_company_id", "product_id"],
            kind="stable",
        ).reset_index(drop=True)

        assert_frame_equal(actual, expected)
        self.assertEqual(tuple(actual.columns), MONTHLY_FACT_COLUMNS)
        for column in DECIMAL_COLUMNS:
            self.assertEqual(actual[column].dtype, object)
            self.assertTrue(
                all(pd.isna(value) or isinstance(value, Decimal) for value in actual[column])
            )

    def test_decimal_null_and_fraction_are_lossless(self) -> None:
        fact = self.fact.copy(deep=True)
        january = fact["month"].eq("202601")
        first = fact.index[january][0]
        second = fact.index[january][1]
        fact.loc[first, "amount_sum_clean"] = Decimal("123.456789")
        fact.loc[first, "amount_valid_row_count"] = 1
        fact.loc[second, "piece_qty_sum"] = pd.NA
        fact.loc[second, "piece_qty_valid_row_count"] = 0

        write_monthly_fact_partitions(fact, self.output_root)
        actual = read_monthly_fact_partitions(self.output_root)
        stored = actual.loc[actual["product_id"].eq(fact.loc[first, "product_id"])]
        self.assertEqual(stored.iloc[0]["amount_sum_clean"], Decimal("123.456789"))
        null_piece = actual.loc[actual["product_id"].eq(fact.loc[second, "product_id"])]
        self.assertTrue(pd.isna(null_piece.iloc[0]["piece_qty_sum"]))

    def test_decimal_precision_and_scale_overflow_are_blocked_before_writes(self) -> None:
        for invalid in (Decimal("0.0000001"), Decimal("1E+32")):
            with self.subTest(invalid=invalid):
                fact = self.fact.copy(deep=True)
                fact.loc[fact.index[0], "amount_sum_clean"] = invalid
                with self.assertRaises(DecimalEncodingError):
                    write_monthly_fact_partitions(fact, self.output_root)
                self.assertFalse(self.output_root.exists())

    def test_arrow_physical_schema_is_explicit(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        parquet_file = pq.ParquetFile(
            partition_dir(self.output_root, "202601") / PARQUET_FILENAME
        )
        stored = parquet_file.schema_arrow.remove_metadata()

        self.assertTrue(stored.equals(ARROW_SCHEMA, check_metadata=False))
        self.assertEqual(stored.field("amount_sum_clean").type, pa.decimal128(38, 6))
        self.assertEqual(stored.field("tx_count").type, pa.int64())
        self.assertEqual(stored.field("month").type, pa.string())
        self.assertEqual(
            {
                parquet_file.metadata.row_group(row_group).column(column).compression
                for row_group in range(parquet_file.metadata.num_row_groups)
                for column in range(parquet_file.metadata.num_columns)
            },
            {"ZSTD"},
        )

    def test_month_filter_prunes_an_unrequested_broken_partition(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        (partition_dir(self.output_root, "202602") / MANIFEST_FILENAME).unlink()

        actual = read_monthly_fact_partitions(self.output_root, months=["202601"])
        self.assertEqual(set(actual["month"]), {"202601"})

    def test_projection_returns_only_requested_columns_and_dtypes(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        actual = read_monthly_fact_partitions(
            self.output_root,
            months=["202602"],
            columns=["month", "tx_count", "amount_sum_clean"],
        )

        self.assertEqual(list(actual.columns), ["month", "tx_count", "amount_sum_clean"])
        self.assertEqual(str(actual["month"].dtype), "string")
        self.assertEqual(str(actual["tx_count"].dtype), "Int64")
        self.assertEqual(actual["amount_sum_clean"].dtype, object)
        self.assertEqual(set(actual["month"]), {"202602"})

    def test_input_order_produces_identical_files_and_second_write_is_noop(self) -> None:
        first_root = self.output_root / "first"
        second_root = self.output_root / "second"
        write_monthly_fact_partitions(self.fact, first_root)
        shuffled = self.fact.sample(frac=1, random_state=42).reset_index(drop=True)
        write_monthly_fact_partitions(shuffled, second_root)

        for month in ("202601", "202602"):
            self.assertEqual(
                manifest(first_root, month)["parquet_sha256"],
                manifest(second_root, month)["parquet_sha256"],
            )
        result = write_monthly_fact_partitions(shuffled, first_root)
        self.assertEqual(result.written_months, ())
        self.assertEqual(result.unchanged_months, ("202601", "202602"))

    def test_identical_partition_winning_publish_race_is_unchanged(self) -> None:
        january = self.fact.loc[self.fact["month"].eq("202601")].copy()
        competitor_root = self.temp_dir / "competitor-identical"
        write_monthly_fact_partitions(january, competitor_root)
        competitor = partition_dir(competitor_root, "202601")

        def publish_race(source: Path, target: Path) -> Path:
            shutil.copytree(competitor, target)
            raise FileExistsError("synthetic identical publisher won")

        with patch.object(
            type(self.output_root),
            "replace",
            autospec=True,
            side_effect=publish_race,
        ):
            result = write_monthly_fact_partitions(january, self.output_root)

        self.assertEqual(result.written_months, ())
        self.assertEqual(result.unchanged_months, ("202601",))
        verify_monthly_fact_partition(self.output_root, "202601")
        schema_root = partition_dir(self.output_root, "202601").parent
        self.assertEqual(list(schema_root.glob(".month=*.tmp-*")), [])

    def test_different_partition_winning_publish_race_is_conflict(self) -> None:
        january = self.fact.loc[self.fact["month"].eq("202601")].copy()
        different = january.copy(deep=True)
        different.loc[different.index[0], "amount_sum_clean"] += Decimal("1")
        competitor_root = self.temp_dir / "competitor-different"
        write_monthly_fact_partitions(different, competitor_root)
        competitor = partition_dir(competitor_root, "202601")

        def publish_race(source: Path, target: Path) -> Path:
            shutil.copytree(competitor, target)
            raise PermissionError("synthetic different publisher won")

        with patch.object(
            type(self.output_root),
            "replace",
            autospec=True,
            side_effect=publish_race,
        ):
            with self.assertRaisesRegex(
                PartitionConflictError, "appeared with different content"
            ):
                write_monthly_fact_partitions(january, self.output_root)

        stored = read_monthly_fact_partitions(self.output_root)
        expected = different.reset_index(drop=True)
        assert_frame_equal(stored, expected)
        schema_root = partition_dir(self.output_root, "202601").parent
        self.assertEqual(list(schema_root.glob(".month=*.tmp-*")), [])

    def test_different_content_cannot_overwrite_existing_month(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        original = verify_monthly_fact_partition(self.output_root, "202601")
        changed = self.fact.copy(deep=True)
        row = changed.index[changed["month"].eq("202601")][0]
        changed.loc[row, "amount_sum_clean"] += Decimal("1")

        with self.assertRaises(PartitionConflictError):
            write_monthly_fact_partitions(changed, self.output_root)
        self.assertEqual(
            verify_monthly_fact_partition(self.output_root, "202601"),
            original,
        )
        self.assertTrue(partition_dir(self.output_root, "202602").is_dir())

    def test_verify_detects_parquet_tampering(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        parquet_path = partition_dir(self.output_root, "202601") / PARQUET_FILENAME
        content = bytearray(parquet_path.read_bytes())
        content[max(8, len(content) // 3)] ^= 1
        parquet_path.write_bytes(content)

        with self.assertRaises(PartitionIntegrityError):
            verify_monthly_fact_partition(self.output_root, "202601")

    def test_manifest_missing_corrupt_and_path_mismatch_are_blocked(self) -> None:
        for mode in ("missing", "corrupt", "path_mismatch"):
            with self.subTest(mode=mode):
                root = self.output_root / mode
                write_monthly_fact_partitions(self.fact, root)
                path = partition_dir(root, "202601") / MANIFEST_FILENAME
                if mode == "missing":
                    path.unlink()
                elif mode == "corrupt":
                    path.write_text("{not-json", encoding="utf-8")
                else:
                    value = json.loads(path.read_text(encoding="utf-8"))
                    value["relative_parquet_path"] = "wrong/part-00000.parquet"
                    path.write_text(
                        json.dumps(
                            value,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        encoding="utf-8",
                    )
                with self.assertRaises(PartitionIntegrityError):
                    read_monthly_fact_partitions(root, months=["202601"])
                with self.assertRaises(PartitionIntegrityError):
                    write_monthly_fact_partitions(self.fact, root)

    def test_invalid_logical_schema_is_blocked_before_file_creation(self) -> None:
        invalid = self.fact.drop(columns=["quality_flags"])
        with self.assertRaises(ValueError):
            write_monthly_fact_partitions(invalid, self.output_root)
        self.assertFalse(self.output_root.exists())

    def test_empty_fact_creates_no_files(self) -> None:
        result = write_monthly_fact_partitions(empty_monthly_fact(), self.output_root)
        self.assertEqual(result.partition_count, 0)
        self.assertEqual(result.input_row_count, 0)
        self.assertFalse(self.output_root.exists())

    def test_writer_does_not_mutate_input(self) -> None:
        before = self.fact.copy(deep=True)
        write_monthly_fact_partitions(self.fact, self.output_root)
        assert_frame_equal(self.fact, before)

    def test_write_failure_cleans_only_temporary_files_and_preserves_partitions(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        before = verify_monthly_fact_partition(self.output_root, "202601")
        schema_root = partition_dir(self.output_root, "202601").parent

        with patch(
            "data_pipeline.storage.monthly_fact_parquet._write_parquet",
            side_effect=OSError("synthetic write failure"),
        ):
            with self.assertRaises(MonthlyFactStorageError):
                write_monthly_fact_partitions(self.fact, self.output_root)

        self.assertEqual(
            verify_monthly_fact_partition(self.output_root, "202601"),
            before,
        )
        self.assertEqual(list(schema_root.glob(".month=*.tmp-*")), [])

    def test_manifest_write_oserror_is_wrapped_and_cleans_only_temp(self) -> None:
        january = self.fact.loc[self.fact["month"].eq("202601")].copy()

        with patch.object(
            type(self.output_root),
            "write_bytes",
            autospec=True,
            side_effect=OSError("synthetic manifest failure"),
        ):
            with self.assertRaisesRegex(
                MonthlyFactStorageError,
                "write canonical manifest for partition 202601",
            ) as raised:
                write_monthly_fact_partitions(january, self.output_root)

        self.assertIsInstance(raised.exception.__cause__, OSError)
        schema_root = partition_dir(self.output_root, "202601").parent
        self.assertFalse(partition_dir(self.output_root, "202601").exists())
        self.assertEqual(list(schema_root.glob(".month=*.tmp-*")), [])

    def test_later_month_failure_preserves_prior_month_and_rerun_resumes(self) -> None:
        from data_pipeline.storage import monthly_fact_parquet as storage

        original_write_parquet = storage._write_parquet

        def fail_february(table: pa.Table, path: Path) -> None:
            if ".month=202602.tmp-" in path.parent.name:
                raise OSError("synthetic February failure")
            original_write_parquet(table, path)

        with patch.object(storage, "_write_parquet", side_effect=fail_february):
            with self.assertRaisesRegex(
                MonthlyFactStorageError,
                "temporary Parquet data for partition 202602",
            ):
                write_monthly_fact_partitions(self.fact, self.output_root)

        january_before = verify_monthly_fact_partition(self.output_root, "202601")
        self.assertFalse(partition_dir(self.output_root, "202602").exists())

        resumed = write_monthly_fact_partitions(self.fact, self.output_root)

        self.assertEqual(resumed.unchanged_months, ("202601",))
        self.assertEqual(resumed.written_months, ("202602",))
        self.assertEqual(
            verify_monthly_fact_partition(self.output_root, "202601"),
            january_before,
        )
        verify_monthly_fact_partition(self.output_root, "202602")

    def test_reader_does_not_hash_files_on_normal_read(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        with patch(
            "data_pipeline.storage.monthly_fact_parquet._sha256_file",
            side_effect=AssertionError("normal reads must not hash full files"),
        ):
            actual = read_monthly_fact_partitions(
                self.output_root,
                months=["202601"],
                columns=["month", "product_id"],
            )
        self.assertFalse(actual.empty)

    def test_unknown_month_and_column_are_explicit_errors(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        with self.assertRaises(InvalidPartitionRequestError):
            read_monthly_fact_partitions(self.output_root, months=["202699"])
        with self.assertRaises(InvalidPartitionRequestError):
            read_monthly_fact_partitions(self.output_root, columns=["unknown"])
        with self.assertRaises(InvalidPartitionRequestError):
            read_monthly_fact_partitions(self.output_root, months=["../202601"])

    def test_manifest_paths_are_portable_and_contain_no_machine_path(self) -> None:
        write_monthly_fact_partitions(self.fact, self.output_root)
        value = manifest(self.output_root, "202601")
        relative = value["relative_parquet_path"]
        self.assertIsInstance(relative, str)
        self.assertNotIn("\\", relative)
        self.assertFalse(Path(relative).is_absolute())
        self.assertNotIn(Path.home().name, relative)


if __name__ == "__main__":
    unittest.main()
