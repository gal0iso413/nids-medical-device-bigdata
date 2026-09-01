from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from data_pipeline.cli.config import FieldRunConfigError, load_field_run_config
import data_pipeline.cli.field_runner as runner
from data_pipeline.contracts import ContractValidationError
from data_pipeline.orchestration import OrchestrationResult
from data_pipeline.storage import MasterLookupBuildResult, MasterLookupVerification
from data_pipeline.storage.monthly_fact_parquet import MonthlyFactStorageError


HASH = "a" * 64


class FieldRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.gettempdir()) / f".field-runner-{uuid4().hex[:10]}"
        self.root.mkdir()
        self.supply_names = (
            "공급내역보고자료(20260101~20260110).xlsx",
            "공급내역보고자료(20260111~20260120).xlsx",
            "공급내역보고자료(20260121~20260131).xlsx",
        )
        self.supply_paths = tuple(self.root / name for name in self.supply_names)
        for path in self.supply_paths:
            path.write_bytes(b"synthetic")
        self.supply = self.supply_paths[0]
        self.lookup_root = self.root / "lookup"
        self.checkpoint_root = self.root / "checkpoint"
        self.output_root = self.root / "output"
        self.lookup_dir = (
            self.lookup_root
            / "master_product_lookup"
            / "schema_version=1.0.0"
            / f"source_hash={HASH}"
        )
        self.lookup_dir.mkdir(parents=True)
        self.lookup_dir.joinpath("master_keys.sqlite").write_bytes(b"sqlite")
        self.lookup_dir.joinpath("_manifest.json").write_text("{}", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def write_config(
        self,
        *,
        master: str | None = None,
        extra: str = "",
        supply_names: tuple[str, ...] | None = None,
    ) -> Path:
        master = master or f'lookup_root = "lookup"\nsource_hash = "{HASH}"'
        names = self.supply_names if supply_names is None else supply_names
        path = self.root / "field-run.toml"
        path.write_text(
            f'''config_version = "1.1.0"
[paths]
supply_workbooks = {list(names)!r}
checkpoint_root = "checkpoint"
output_root = "output"
[master]
{master}
[run]
batch_size = 100
max_month_fact_bytes = 1000000
minimum_free_bytes = 0
{extra}
''',
            encoding="utf-8",
        )
        return path

    def two_month_config(self):
        february = (
            "공급내역보고자료(20260201~20260210).xlsx",
            "공급내역보고자료(20260211~20260220).xlsx",
            "공급내역보고자료(20260221~20260228).xlsx",
        )
        for name in february:
            (self.root / name).write_bytes(b"synthetic")
        return load_field_run_config(
            self.write_config(supply_names=self.supply_names + february)
        )

    def config(self, **kwargs):
        return load_field_run_config(self.write_config(**kwargs))

    def test_config_resolves_relative_paths_and_exact_values(self) -> None:
        config = self.config()
        self.assertEqual(config.supply_workbooks, self.supply_paths)
        self.assertEqual(config.master_lookup_root, self.lookup_root)
        self.assertEqual(config.checkpoint_root, self.checkpoint_root)
        self.assertEqual(config.batch_size, 100)
        self.assertEqual(config.max_month_fact_bytes, 1_000_000)

    def test_config_requires_exactly_one_master_source(self) -> None:
        with self.assertRaisesRegex(FieldRunConfigError, "exactly one"):
            self.config(master='lookup_root = "lookup"')
        with self.assertRaisesRegex(FieldRunConfigError, "exactly one"):
            self.config(
                master=f'lookup_root = "lookup"\nsource_hash = "{HASH}"\nworkbooks = ["master.xlsx"]'
            )

    def test_config_rejects_unknown_fields_and_bad_numbers(self) -> None:
        with self.assertRaisesRegex(FieldRunConfigError, "unsupported"):
            self.config(extra="surprise = true")
        with self.assertRaisesRegex(FieldRunConfigError, "positive"):
            path = self.write_config()
            path.write_text(path.read_text(encoding="utf-8").replace("batch_size = 100", "batch_size = 0"), encoding="utf-8")
            load_field_run_config(path)

    def test_preflight_is_light_and_does_not_compute_lineage(self) -> None:
        with patch.object(runner, "create_source_lineage", side_effect=AssertionError("checksum forbidden")), patch.object(
            runner, "create_master_lineage", side_effect=AssertionError("Excel traversal forbidden")
        ), patch.object(runner, "verify_master_product_lookup", side_effect=AssertionError("full verify forbidden")):
            report = runner.run_preflight(self.config())
        self.assertTrue(report.ok)
        self.assertIn("warn", {check.status for check in report.checks})

    def test_preflight_fails_missing_input_without_absolute_path(self) -> None:
        self.supply.unlink()
        report = runner.run_preflight(self.config())
        check = next(item for item in report.checks if item.name == "supply_workbooks")
        self.assertEqual(check.status, "fail")
        self.assertIn(self.supply.name, check.detail)
        self.assertNotIn(str(self.root), check.detail)

    def test_input_diagnostics_are_bounded_to_twenty_names(self) -> None:
        missing = tuple(self.root / f"missing-{number:02d}.xlsx" for number in range(25))
        check = runner._check_readable_inputs(missing, "supply_workbooks")
        self.assertEqual(check.status, "fail")
        self.assertIn("total=25", check.detail)
        self.assertIn("omitted=5", check.detail)
        self.assertEqual(check.detail.count("missing-"), 20)

    def test_preflight_blocks_nested_checkpoint_and_output(self) -> None:
        path = self.write_config()
        path.write_text(
            path.read_text(encoding="utf-8").replace('output_root = "output"', 'output_root = "checkpoint/output"'),
            encoding="utf-8",
        )
        report = runner.run_preflight(load_field_run_config(path))
        check = next(item for item in report.checks if item.name == "checkpoint_output_disjoint")
        self.assertEqual(check.status, "fail")

    def test_preflight_write_probe_leaves_no_artifact(self) -> None:
        report = runner.run_preflight(self.config())
        self.assertTrue(report.ok)
        self.assertEqual(list(self.root.glob(".nids-write-probe-*")), [])

    def test_preflight_inventory_distinguishes_states(self) -> None:
        version_root = self.checkpoint_root / "supply_monthly_orchestration" / "checkpoint_version=1.0.0"
        for run_id, marker in (
            ("1" * 64, "checkpoint.sqlite"),
            ("2" * 64, "_sealed_manifest.json"),
            ("3" * 64, "_complete_manifest.json"),
            ("4" * 64, "unknown"),
        ):
            directory = version_root / f"run_id={run_id}"
            directory.mkdir(parents=True)
            directory.joinpath(marker).touch()
            if marker == "checkpoint.sqlite":
                directory.joinpath("_run_manifest.json").touch()
        check = runner._checkpoint_inventory(self.config())
        self.assertEqual(check.status, "warn")
        self.assertIn("active=1", check.detail)
        self.assertIn("sealed=1", check.detail)
        self.assertIn("complete=1", check.detail)
        self.assertIn("incomplete=1", check.detail)

    def test_run_delegates_to_existing_orchestration_and_replay_contract(self) -> None:
        config = self.config()
        first = OrchestrationResult("completed", "b" * 64, ("202601",), (), (), "relative.json")
        second = OrchestrationResult("unchanged", "b" * 64, (), ("202601",), (), "relative.json")
        with patch.object(runner, "run_preflight", return_value=runner.PreflightReport(True, ())), patch.object(
            runner, "run_supply_monthly_orchestration", side_effect=(first, second)
        ) as orchestration:
            one = runner.run_pipeline(config)
            two = runner.run_pipeline(config)
        self.assertEqual(one["status"], "completed")
        self.assertEqual(two["status"], "unchanged")
        self.assertEqual(orchestration.call_count, 2)
        for call in orchestration.call_args_list:
            self.assertEqual(tuple(call.kwargs["supply_paths"]), self.supply_paths)
            self.assertEqual(call.kwargs["batch_size"], config.batch_size)
        self.assertEqual(one["skipped_source_error_months"], [])

    def test_run_skips_source_conflict_and_continues_next_month(self) -> None:
        config = self.two_month_config()
        conflict = ContractValidationError(
            "blocked:source_row_conflict: identical idempotency keys contain "
            "different normalized content; conflicting source_row_id values: "
            "total=1; sample=['nids-row-v1:ab']; omitted=0"
        )
        second = OrchestrationResult("completed", "c" * 64, ("202602",), (), (), "relative.json")
        with patch.object(runner, "run_preflight", return_value=runner.PreflightReport(True, ())), patch.object(
            runner, "run_supply_monthly_orchestration", side_effect=(conflict, second)
        ) as orchestration, patch.object(runner, "_write_json"):
            payload = runner.run_pipeline(config)
        self.assertEqual(orchestration.call_count, 2)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["skipped_source_error_months"], ["202601"])
        self.assertEqual(payload["written_months"], ["202602"])
        self.assertEqual(payload["months"][0]["status"], "skipped_source_error")
        self.assertEqual(payload["months"][0]["error"], "ContractValidationError")
        self.assertEqual(payload["months"][1]["status"], "completed")

    def test_run_stops_on_wrapped_os_error_without_skipping_later_months(self) -> None:
        config = self.two_month_config()

        def locked(*args, **kwargs):
            del args, kwargs
            raise MonthlyFactStorageError(
                "Could not publish final partition 202601; no competing "
                "partition is available for verification"
            ) from PermissionError(5, "Access is denied")

        with patch.object(runner, "run_preflight", return_value=runner.PreflightReport(True, ())), patch.object(
            runner, "run_supply_monthly_orchestration", side_effect=locked
        ) as orchestration:
            with self.assertRaises(MonthlyFactStorageError):
                runner.run_pipeline(config)
        self.assertEqual(orchestration.call_count, 1)

    def test_master_workbook_mode_calls_existing_builder(self) -> None:
        master = self.root / "synthetic-master.xlsx"
        master.write_bytes(b"synthetic-master")
        config = self.config(master='lookup_root = "lookup"\nworkbooks = ["synthetic-master.xlsx"]')
        built = MasterLookupBuildResult("written", "version", HASH, "relative", 1, 1, 1, 0, 0, (), 0)
        result = OrchestrationResult("completed", "b" * 64, (), (), (), "relative.json")
        with patch.object(runner, "run_preflight", return_value=runner.PreflightReport(True, ())), patch.object(
            runner, "build_master_product_lookup", return_value=built
        ) as builder, patch.object(runner, "run_supply_monthly_orchestration", return_value=result) as orchestration:
            runner.run_pipeline(config)
        builder.assert_called_once_with(config.master_workbooks, config.master_lookup_root, batch_size=100)
        self.assertEqual(orchestration.call_args.kwargs["master_source_hash"], HASH)

    def test_status_reports_each_artifact_state_without_claiming_verification(self) -> None:
        config = self.config()
        run_id = "b" * 64
        with patch.object(runner, "_runtime_identity", return_value=(run_id, HASH)):
            self.assertEqual(runner.read_status(config)["state"], "not_started")
            run_dir = runner._run_dir(config, run_id)
            run_dir.mkdir(parents=True)
            run_dir.joinpath("_run_manifest.json").touch()
            run_dir.joinpath("checkpoint.sqlite").touch()
            self.assertEqual(runner.read_status(config)["state"], "active")
            run_dir.joinpath("_sealed_manifest.json").touch()
            self.assertEqual(runner.read_status(config)["state"], "sealed_unpublished_or_incomplete")
            run_dir.joinpath("_complete_manifest.json").touch()
            payload = runner.read_status(config)
            self.assertEqual(payload["state"], "complete_unverified")
            self.assertFalse(payload["verified"])

    def test_status_reports_missing_master_lookup_without_building_it(self) -> None:
        config = self.config()
        shutil.rmtree(self.lookup_root)
        with patch.object(runner, "build_master_product_lookup") as builder, patch.object(
            runner, "create_source_lineage"
        ) as supply_lineage:
            payload = runner.read_status(config)
        self.assertEqual(payload["state"], "master_lookup_missing")
        self.assertIsNone(payload["run_id"])
        builder.assert_not_called()
        supply_lineage.assert_not_called()

    def test_verify_requires_complete_and_sealed_before_orchestration(self) -> None:
        config = self.config()
        run_id = "b" * 64
        with patch.object(runner, "_runtime_identity", return_value=(run_id, HASH)), patch.object(
            runner, "run_supply_monthly_orchestration"
        ) as orchestration:
            with self.assertRaisesRegex(runner.FieldRunVerificationError, "complete"):
                runner.verify_completed_run(config)
        orchestration.assert_not_called()

    def test_verify_reuses_existing_verifiers_and_complete_state_path(self) -> None:
        config = self.config()
        run_id = "b" * 64
        run_dir = runner._run_dir(config, run_id)
        run_dir.mkdir(parents=True)
        run_dir.joinpath("_complete_manifest.json").touch()
        run_dir.joinpath("_sealed_manifest.json").touch()
        sealed = Mock(months=("202601",), ledger_rows=2, matched_rows=1, unmatched_rows=1)
        result = OrchestrationResult("unchanged", run_id, (), ("202601",), (), "relative.json")
        with patch.object(runner, "_runtime_identity", return_value=(run_id, HASH)), patch.object(
            runner, "verify_sealed_supply_checkpoint", return_value=sealed
        ) as verifier, patch.object(runner, "run_supply_monthly_orchestration", return_value=result) as orchestration:
            payload = runner.verify_completed_run(config)
        verifier.assert_called_once_with(config.checkpoint_root, run_id)
        orchestration.assert_called_once()
        self.assertEqual(payload["status"], "verified")
        self.assertEqual(payload["months"][0]["months"], ["202601"])

    def test_cli_exit_codes_and_bounded_json(self) -> None:
        stdout, stderr = StringIO(), StringIO()
        with patch.object(runner, "run_preflight", return_value=runner.PreflightReport(False, (runner.PreflightCheck("x", "fail", "bad"),))):
            code = runner.main(["preflight", "--config", str(self.write_config())], stdout=stdout, stderr=stderr)
        self.assertEqual(code, runner.EXIT_PREFLIGHT)
        self.assertFalse(json.loads(stdout.getvalue())["ok"])
        stdout, stderr = StringIO(), StringIO()
        code = runner.main(["run", "--config", str(self.root / "missing.toml")], stdout=stdout, stderr=stderr)
        self.assertEqual(code, runner.EXIT_CONFIG)
        self.assertEqual(json.loads(stderr.getvalue())["stage"], "config")

    def test_error_output_redacts_known_absolute_paths(self) -> None:
        config = self.config()
        message = runner._safe_error_message(RuntimeError(f"failure at {config.output_root.resolve()}"), config)
        self.assertNotIn(str(self.root), message)
        self.assertIn("<output>", message)


if __name__ == "__main__":
    unittest.main()
