from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from data_pipeline.analysis.class2_serving_mart import SERVING_MART_SCHEMA_VERSION, build_class2_serving_marts
from data_pipeline.storage.monthly_fact_parquet import write_monthly_fact_partitions
from services.class2_local_api.app import StaticRootError, create_app, create_integrated_app
from tests.services.test_class2_local_api import fact


class Class2LocalIntegratedHostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="class2-local-host-"))
        self.facts, self.marts, self.static = self.root / "facts", self.root / "marts", self.root / "static"
        write_monthly_fact_partitions(fact([
            {"product_id": "p3:" + "1" * 64, "item_group_id": "Group A", "item_name_id": "Item A", "amount_sum_clean": Decimal("12.500000")},
            {"product_id": "p3:" + "2" * 64, "item_group_id": "Group B", "item_name_id": "Item B", "src_company_id": "co:other", "dst_company_id": "hosp:other"},
        ]), self.facts)
        build_class2_serving_marts(fact_root=self.facts, output_root=self.marts, period_start="202401", period_end="202401")
        (self.static / "assets").mkdir(parents=True)
        (self.static / "index.html").write_text("<!doctype html><title>Class 2 local</title><div id=app></div>", encoding="utf-8")
        (self.static / "assets" / "app.js").write_text("console.log('local only')", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def client(self) -> TestClient:
        return TestClient(create_integrated_app(self.marts, self.static))

    def test_static_deep_links_and_existing_api_are_served_by_one_origin(self) -> None:
        payload = {"period_start": "202401", "period_end": "202401", "selections": [{"selection_type": "item_group", "item_group_id": "Group A"}]}
        with self.client() as client:
            root = client.get("/")
            deep_link = client.get("/comparisons/monthly")
            asset = client.get("/assets/app.js")
            health = client.get("/api/healthz")
            status = client.get("/api/v1/status")
            catalog = client.get("/api/v1/catalog/item-groups", params={"q": "Group"})
            comparison = client.post("/api/v1/comparisons", json=payload)
            api_missing = client.get("/api/not-an-spa-route")
        self.assertEqual(root.status_code, 200)
        self.assertEqual(deep_link.content, root.content)
        self.assertEqual(asset.text, "console.log('local only')")
        self.assertEqual(health.json()["service_mode"], "local_internal_only")
        self.assertEqual(status.json()["public_release_policy"], "not_approved")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(comparison.status_code, 200)
        self.assertEqual(api_missing.status_code, 404)
        self.assertNotIn("Class 2 local", api_missing.text)

    def test_static_root_rejections_and_api_only_regression(self) -> None:
        with self.assertRaises(StaticRootError):
            create_integrated_app(self.marts, self.root / "missing")
        missing_index = self.root / "missing-index"; missing_index.mkdir()
        with self.assertRaises(StaticRootError): create_integrated_app(self.marts, missing_index)
        mart_dir = self.marts / "class2_serving_mart" / f"schema_version={SERVING_MART_SCHEMA_VERSION}"
        (mart_dir / "index.html").write_text("not served", encoding="utf-8")
        with self.assertRaises(StaticRootError): create_integrated_app(self.marts, mart_dir)
        (self.static / "generated").mkdir()
        (self.static / "generated" / "raw.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(StaticRootError): create_integrated_app(self.marts, self.static)
        shutil.rmtree(self.static / "generated")
        (self.static / "assets" / "unsafe.js").write_text("const endpoint = 'co:private';", encoding="utf-8")
        with self.assertRaises(StaticRootError): create_integrated_app(self.marts, self.static)
        (self.static / "assets" / "unsafe.js").unlink()
        (self.static / "assets" / "react-url.js").write_text(
            "const u='https://react.dev/errors/'; const svg='http://www.w3.org/2000/svg';", encoding="utf-8"
        )
        create_integrated_app(self.marts, self.static)
        (self.static / "assets" / "winpath.js").write_text("const p='C:\\\\Users\\\\nids';", encoding="utf-8")
        with self.assertRaises(StaticRootError): create_integrated_app(self.marts, self.static)
        (self.static / "assets" / "react-url.js").unlink()
        (self.static / "assets" / "winpath.js").unlink()
        api = create_app(self.marts)
        with TestClient(api) as client:
            self.assertEqual(client.get("/healthz").status_code, 200)

    def test_static_and_http_responses_do_not_expose_private_data_or_paths(self) -> None:
        with self.client() as client:
            responses = [client.get("/").text, client.get("/assets/app.js").text, client.get("/api/v1/status").text]
        rendered = json.dumps(responses)
        for forbidden in ("src_company_id", "dst_company_id", "co:", "hosp:", str(self.root), "_manifest.json", ".parquet"):
            self.assertNotIn(forbidden, rendered)
        escaped = create_integrated_app(self.marts, self.static)
        (self.static / "generated").mkdir()
        (self.static / "generated" / "raw.json").write_text("{}", encoding="utf-8")
        with TestClient(escaped) as client:
            self.assertEqual(client.get("/../_manifest.json").status_code, 404)
            self.assertEqual(client.get("/generated/raw.json").status_code, 404)


if __name__ == "__main__":
    unittest.main()
