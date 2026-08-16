from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from data_pipeline.analysis.class3_serving_mart import (
    SERVING_MART_DATASET_NAME,
    SERVING_MART_SCHEMA_VERSION,
    build_class3_serving_marts,
)
from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from data_pipeline.privacy.class3_release_policy import (
    DATASET_NAME,
    POLICY_VERSION,
    ReleasePolicyConflictError,
    ReleasePolicyError,
    evaluate_class3_release_policy,
)
from data_pipeline.storage.monthly_fact_parquet import write_monthly_fact_partitions


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _fact(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults: dict[str, object] = {
        "month": "202401", "src_company_id": "co:alpha", "dst_company_id": "hosp:x",
        "product_id": "p3:" + "1" * 64, "item_group_id": "group-1", "item_name_id": "name-1",
        "tx_count": 1, "amount_sum_clean": Decimal("1.000000"), "amount_valid_row_count": 1,
        "raw_supply_qty_sum": Decimal("1.000000"), "raw_supply_qty_valid_row_count": 1,
        "piece_qty_sum": Decimal("1.000000"), "piece_qty_valid_row_count": 1,
        "unique_udi_count": 1, "active_day_count": 1, "supplier_type": "manufacturer",
        "receiver_type": "hospital", "supplier_region": "11", "receiver_region": "26",
        "source_version": "synthetic", "quality_flags": "",
    }
    frame = pd.concat([empty_monthly_fact(), pd.DataFrame([{**defaults, **row} for row in rows])], ignore_index=True)
    for column in ("month", "src_company_id", "dst_company_id", "product_id", "item_group_id", "item_name_id", "supplier_type", "receiver_type", "supplier_region", "receiver_region", "source_version", "quality_flags"):
        frame[column] = frame[column].astype("string")
    for column in ("tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count", "piece_qty_valid_row_count", "unique_udi_count", "active_day_count"):
        frame[column] = frame[column].astype("Int64")
    return frame


class Class3ReleasePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="class3-release-policy-"))
        self.fact_root = self.root / "facts"
        self.mart_output = self.root / "marts"
        self.output = self.root / "artifacts"
        self.p1, self.p2, self.p3 = ("p3:" + digit * 64 for digit in "123")
        write_monthly_fact_partitions(_fact([
            {"product_id": self.p1, "src_company_id": "co:alpha", "dst_company_id": "hosp:x", "amount_sum_clean": Decimal("90.000000")},
            {"product_id": self.p1, "src_company_id": "co:beta", "dst_company_id": "hosp:y", "amount_sum_clean": Decimal("10.000000")},
            {"product_id": self.p2, "src_company_id": "co:single", "dst_company_id": "hosp:single", "amount_sum_clean": Decimal("4.000000")},
            {"product_id": self.p3, "src_company_id": "co:gamma", "dst_company_id": "hosp:z", "amount_sum_clean": None, "amount_valid_row_count": 0},
            {"product_id": self.p3, "src_company_id": "co:delta", "dst_company_id": "hosp:w", "amount_sum_clean": None, "amount_valid_row_count": 0},
        ]), self.fact_root)
        build_class3_serving_marts(fact_root=self.fact_root, output_root=self.mart_output, period_start="202401", period_end="202401")
        self.mart_root = self.mart_output / SERVING_MART_DATASET_NAME / f"schema_version={SERVING_MART_SCHEMA_VERSION}"

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def policy(self, **changes: object) -> Path:
        value = {
            "policy_version": POLICY_VERSION, "approval_status": "not_approved",
            "differencing_protection": "not_implemented", "minimum_endpoint_count": 2,
            "minimum_coverage_rate": 1.0, "dominance_threshold": 0.8,
            **changes,
        }
        path = self.root / f"policy-{len(list(self.root.glob('policy-*.json')))}.json"
        path.write_bytes(_canonical(value))
        return path

    def evaluate(self, policy: Path, *, output: Path | None = None, **kwargs: object):
        return evaluate_class3_release_policy(
            mart_root=self.mart_root, policy_config=policy, output_root=output or self.output,
            period_start="202401", period_end="202401", scopes=(("product", self.p1), ("product", self.p2), ("product", self.p3)), **kwargs,
        )

    def artifact(self, output: Path | None = None) -> dict[str, object]:
        path = (output or self.output) / DATASET_NAME / f"schema_version={POLICY_VERSION}" / "release-status.json"
        raw = path.read_bytes(); value = json.loads(raw)
        self.assertEqual(raw, _canonical(value))
        return value

    def test_default_policy_is_fail_closed_and_artifact_is_canonical_private(self) -> None:
        result = self.evaluate(self.policy())
        self.assertEqual(result.status, "written")
        artifact = self.artifact()
        self.assertEqual({entry["status"] for entry in artifact["entries"]}, {"not_approved"})
        self.assertEqual(artifact["differencing_attack_protection"], "not_implemented")
        manifest_path = self.output / DATASET_NAME / f"schema_version={POLICY_VERSION}" / "_manifest.json"
        serialised = json.dumps(artifact, sort_keys=True) + manifest_path.read_text(encoding="utf-8")
        for forbidden in ("src_company_id", "dst_company_id", "co:", "hosp:", "90.000000", "100.000000", "share", "numerator", "denominator"):
            self.assertNotIn(forbidden, serialised)
        self.assertEqual(manifest_path.read_bytes(), _canonical(json.loads(manifest_path.read_bytes())))

    def test_approved_static_rules_apply_small_cell_coverage_dominance_and_pending_differencing(self) -> None:
        approved = self.policy(approval_status="approved", differencing_protection="implemented")
        self.evaluate(approved, fact_root=self.fact_root)
        states = {entry["scope_id"]: entry["status"] for entry in self.artifact()["entries"]}
        self.assertEqual(states, {self.p1: "suppressed_dominance", self.p2: "suppressed_small_cell", self.p3: "suppressed_insufficient_coverage"})
        pending = self.policy(approval_status="approved", dominance_threshold=1.0)
        self.evaluate(pending, output=self.root / "pending")
        self.assertEqual({entry["status"] for entry in self.artifact(self.root / "pending")["entries"]}, {"not_approved", "suppressed_small_cell", "suppressed_insufficient_coverage"})

    def test_deterministic_unchanged_conflict_roots_and_staging_cleanup(self) -> None:
        policy = self.policy(approval_status="approved", differencing_protection="implemented", dominance_threshold=1.0)
        first = self.evaluate(policy)
        status_path = first.output_path / "release-status.json"
        original = status_path.read_bytes()
        self.assertEqual(self.evaluate(policy).status, "unchanged")
        self.assertEqual(status_path.read_bytes(), original)
        with self.assertRaises(ReleasePolicyConflictError):
            self.evaluate(self.policy(approval_status="approved", differencing_protection="implemented", dominance_threshold=0.8))
        with self.assertRaises(ReleasePolicyError): self.evaluate(policy, output=self.mart_root)
        with self.assertRaises(ReleasePolicyError): self.evaluate(policy, output=self.root / "checkpoint", checkpoint_root=self.root / "checkpoint")
        failed = self.root / "failed"
        import data_pipeline.privacy.class3_release_policy as policy_module
        with patch.object(policy_module.os, "replace", side_effect=OSError("synthetic publish failure")):
            with self.assertRaises(OSError): self.evaluate(policy, output=failed)
        parent = failed / DATASET_NAME
        self.assertEqual(list(parent.glob(".schema_version=*.tmp-*") if parent.exists() else []), [])

    def test_rejects_manifest_fingerprint_checksum_schema_and_invalid_inputs(self) -> None:
        manifest_path = self.mart_root / "_manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["created_fingerprint"] = "0" * 64
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(ReleasePolicyError, "fingerprint"):
            self.evaluate(self.policy())
        manifest = json.loads((self.mart_root / "_manifest.json").read_bytes())
        manifest["output_sha256"]["product_month"] = "0" * 64
        fingerprint_input = {key: value for key, value in manifest.items() if key not in {"created_fingerprint", "outputs"}}
        manifest["created_fingerprint"] = sha256(_canonical(fingerprint_input)).hexdigest()
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(ReleasePolicyError, "checksum"):
            self.evaluate(self.policy())
        manifest["serving_mart_schema_version"] = "0.0.0"
        fingerprint_input = {key: value for key, value in manifest.items() if key not in {"created_fingerprint", "outputs"}}
        manifest["created_fingerprint"] = sha256(_canonical(fingerprint_input)).hexdigest()
        manifest_path.write_bytes(_canonical(manifest))
        with self.assertRaisesRegex(ReleasePolicyError, "schema"):
            self.evaluate(self.policy())
        bad = self.root / "bad-policy.json"; bad.write_text("{}", encoding="utf-8")
        with self.assertRaises(ReleasePolicyError): self.evaluate(bad)
        with self.assertRaises(ReleasePolicyError):
            evaluate_class3_release_policy(mart_root=self.mart_root, policy_config=self.policy(), output_root=self.root / "empty", period_start="202401", period_end="202401", scopes=())


if __name__ == "__main__":
    unittest.main()
