import importlib.util, json, tempfile, unittest
from pathlib import Path

_path = Path(__file__).parents[2] / "tools/offline/analysis-kit/source_snapshot.py"
_spec = importlib.util.spec_from_file_location("analysis_snapshot", _path)
_module = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_module)
canonical, create_snapshot = _module.canonical, _module.create_snapshot


class SourceSnapshotTests(unittest.TestCase):
    def test_working_tree_manifest_is_canonical_and_deterministic(self):
        root = Path(__file__).parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            first = create_snapshot(root, Path(temporary) / "one")
            second = create_snapshot(root, Path(temporary) / "two")
            self.assertEqual(first["source_tree_fingerprint"], second["source_tree_fingerprint"])
            self.assertEqual(first["source_mode"], "working-tree")
            self.assertIn("tools/offline/analysis-kit/source_snapshot.py", [x["relative_path"] for x in first["files"]])
            self.assertIn("services/class3_local_api/app.py", [x["relative_path"] for x in first["files"]])
            self.assertIn("services/class1_local_api/app.py", [x["relative_path"] for x in first["files"]])
            self.assertIn("data_pipeline/analysis/class1_lookup_index.py", [x["relative_path"] for x in first["files"]])
            self.assertIn("data_pipeline/ingest/company_display_name.py", [x["relative_path"] for x in first["files"]])
            self.assertIn("docs/service/class1-local-integrated-host.md", [x["relative_path"] for x in first["files"]])
            raw = (Path(temporary) / "one/source-snapshot-manifest.json").read_bytes()
            self.assertEqual(raw, canonical(json.loads(raw)) + b"\n")
            self.assertNotIn(str(root).encode(), raw)
