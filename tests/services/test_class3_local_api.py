from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import pandas as pd
from fastapi.testclient import TestClient

from data_pipeline.analysis.class3_serving_mart import build_class3_serving_marts
from data_pipeline.contracts.supply_monthly import empty_monthly_fact
from data_pipeline.storage.monthly_fact_parquet import write_monthly_fact_partitions
from services.class3_local_api.app import create_app
from services.class3_local_api.reader import MartVerificationError


def fact(rows: list[dict[str, object]]) -> pd.DataFrame:
    defaults: dict[str, object] = {
        "month": "202401", "src_company_id": "co:raw-supplier", "dst_company_id": "hosp:raw-receiver",
        "product_id": "p3:" + "1" * 64, "item_group_id": "Group A", "item_name_id": "Item A",
        "tx_count": 1, "amount_sum_clean": Decimal("12.500000"), "amount_valid_row_count": 1,
        "raw_supply_qty_sum": Decimal("2.000000"), "raw_supply_qty_valid_row_count": 1,
        "piece_qty_sum": Decimal("3.000000"), "piece_qty_valid_row_count": 1,
        "unique_udi_count": 1, "active_day_count": 1, "supplier_type": "manufacturer",
        "receiver_type": "hospital", "supplier_region": "11", "receiver_region": "26",
        "source_version": "synthetic", "quality_flags": "",
    }
    frame = pd.concat([empty_monthly_fact(), pd.DataFrame([{**defaults, **row} for row in rows])], ignore_index=True)
    strings = ("month", "src_company_id", "dst_company_id", "product_id", "item_group_id", "item_name_id", "supplier_type", "receiver_type", "supplier_region", "receiver_region", "source_version", "quality_flags")
    counts = ("tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count", "piece_qty_valid_row_count", "unique_udi_count", "active_day_count")
    for column in strings:
        frame[column] = frame[column].astype("string")
    for column in counts:
        frame[column] = frame[column].astype("Int64")
    return frame


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


class Class3LocalApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="class3-api-"))
        self.facts = self.root / "facts"
        self.marts = self.root / "marts"
        write_monthly_fact_partitions(fact([
            {"product_id": "p3:" + "1" * 64, "item_group_id": "Group A", "item_name_id": "Shared", "amount_sum_clean": Decimal("12.500000")},
            {"product_id": "p3:" + "2" * 64, "item_group_id": "Group A", "item_name_id": "Other", "src_company_id": "co:other", "dst_company_id": "hosp:other"},
            {"product_id": "p3:" + "3" * 64, "item_group_id": "Group B", "item_name_id": "Shared", "month": "202402", "amount_sum_clean": Decimal("7.000000")},
        ]), self.facts)
        build_class3_serving_marts(fact_root=self.facts, output_root=self.marts, period_start="202401", period_end="202402")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def client(self) -> TestClient:
        return TestClient(create_app(self.marts))

    def manifest_path(self) -> Path:
        return self.marts / "class3_serving_mart" / "schema_version=1.0.0" / "_manifest.json"

    def test_health_status_catalog_and_decimal_string(self) -> None:
        with self.client() as client:
            health = client.get("/healthz")
            status = client.get("/v1/status")
            groups = client.get("/v1/catalog/item-groups", params={"q": "group", "limit": 999})
            names = client.get("/v1/catalog/item-names", params={"item_group_id": "Group A"})
            comparison = client.post("/v1/comparisons", json={"period_start": "202401", "period_end": "202402", "selections": [{"selection_type": "item_name", "item_group_id": "Group A", "item_name_id": "Shared"}]})
        self.assertEqual(health.status_code, 200)
        self.assertEqual(status.json()["service_mode"], "local_internal_only")
        self.assertEqual(status.json()["public_release_policy"], "not_approved")
        self.assertEqual(groups.json()["limit"], 50)
        self.assertEqual({row["item_group_id"] for row in groups.json()["items"]}, {"Group A", "Group B"})
        self.assertEqual({row["item_name_id"] for row in names.json()["items"]}, {"Other", "Shared"})
        self.assertEqual(comparison.status_code, 200)
        self.assertEqual(comparison.json()["product_catalog"], [{"product_id": "p3:" + "1" * 64, "item_group_id": "Group A", "item_name_id": "Shared"}])
        self.assertIsInstance(comparison.json()["product_month"][0]["amount_sum_clean"], str)

    def test_scope_request_limits_and_sql_like_query_are_bounded(self) -> None:
        with self.client() as client:
            self.assertEqual(client.get("/v1/catalog/item-names").status_code, 422)
            self.assertEqual(client.get("/v1/catalog/item-groups", params={"q": "' OR 1=1 --"}).json()["items"], [])
            outside = client.post("/v1/comparisons", json={"period_start": "202312", "period_end": "202401", "selections": [{"selection_type": "item_group", "item_group_id": "Group A"}]})
            too_many = client.post("/v1/comparisons", json={"period_start": "202401", "period_end": "202402", "selections": [{"selection_type": "item_group", "item_group_id": "Group A"}] * 11})
            bad_selection = client.post("/v1/comparisons", json={"period_start": "202401", "period_end": "202402", "selections": [{"selection_type": "item_name", "item_group_id": "Group A"}]})
        self.assertEqual(outside.status_code, 422)
        self.assertEqual(too_many.status_code, 422)
        self.assertEqual(bad_selection.status_code, 422)

    def test_manifest_tampering_blocks_startup(self) -> None:
        path = self.manifest_path()
        original = json.loads(path.read_text(encoding="utf-8"))
        fingerprint_keys = ("serving_mart_dataset_name", "serving_mart_schema_version", "fact_dataset_name", "fact_schema_version", "fact_schema_fingerprint", "period_start", "period_end", "source_partitions", "output_sha256")

        def refresh_fingerprint(value: dict[str, object]) -> dict[str, object]:
            value["created_fingerprint"] = sha256(canonical({key: value[key] for key in fingerprint_keys})).hexdigest()
            return value

        cases = []
        bad_checksum = refresh_fingerprint({**original, "output_sha256": {**original["output_sha256"], "coverage": "0" * 64}})
        cases.append(bad_checksum)
        bad_schema = {**original, "serving_mart_schema_version": "999.0.0"}
        cases.append(bad_schema)
        bad_fingerprint = {**original, "created_fingerprint": "0" * 64}
        cases.append(bad_fingerprint)
        bad_path = json.loads(json.dumps(original))
        bad_path["outputs"][0]["filename"] = "../outside.parquet"
        cases.append(refresh_fingerprint(bad_path))
        for value in cases:
            path.write_bytes(canonical(value))
            with self.assertRaises(MartVerificationError):
                create_app(self.marts)
        path.write_bytes(canonical(original))
        create_app(self.marts).state.mart_reader.close()

    def test_period_larger_than_36_months_is_blocked_inside_manifest_range(self) -> None:
        path = self.manifest_path()
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["period_start"], manifest["period_end"] = "202001", "202401"
        keys = ("serving_mart_dataset_name", "serving_mart_schema_version", "fact_dataset_name", "fact_schema_version", "fact_schema_fingerprint", "period_start", "period_end", "source_partitions", "output_sha256")
        manifest["created_fingerprint"] = sha256(canonical({key: manifest[key] for key in keys})).hexdigest()
        path.write_bytes(canonical(manifest))
        with self.client() as client:
            response = client.post("/v1/comparisons", json={"period_start": "202001", "period_end": "202401", "selections": [{"selection_type": "item_group", "item_group_id": "Group A"}]})
        self.assertEqual(response.status_code, 422)

    def test_response_has_no_raw_endpoint_identifiers_and_is_deterministic(self) -> None:
        payload = {"period_start": "202401", "period_end": "202402", "selections": [{"selection_type": "item_group", "item_group_id": "Group A"}]}
        with self.client() as client:
            first = client.post("/v1/comparisons", json=payload).json()
            second = client.post("/v1/comparisons", json=payload).json()
        self.assertEqual(first, second)
        rendered = json.dumps(first, sort_keys=True)
        for prohibited in ("src_company_id", "dst_company_id", "co:raw", "hosp:raw", "co:other", "hosp:other"):
            self.assertNotIn(prohibited, rendered)


if __name__ == "__main__":
    unittest.main()
