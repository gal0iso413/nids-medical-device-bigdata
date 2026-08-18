from __future__ import annotations

from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
REMOVED_PATHS = (
    "class_1_anomaly_detection/app.py",
    "class_1_anomaly_detection/src/eda",
    "class_1_anomaly_detection/src/experiments",
    "class_1_anomaly_detection/src/graph",
    "class_1_anomaly_detection/src/ingest",
    "class_1_anomaly_detection/tests/test_network_build_smoke.py",
    "class_1_anomaly_detection/.cursor",
    "class_1_anomaly_detection/.env.example",
    "class_1_anomaly_detection/notes",
    "class_1_anomaly_detection/research",
    "class_3_impact_evaluation",
    "prototype_meeting",
    "class_2_supply_forecast",
    ".hermes",
    "scripts/notify_hermes_deliverable.py",
    "shared_utils",
    "requirements.txt",
    "shared_data",
    "docs/migration",
    "docs/archive",
    "docs/architecture",
    "shared_docs/structured/class_1_anomaly_spec.md",
    "shared_docs/structured/class_2_forecast_spec.md",
    "shared_docs/structured/class_3_evaluation_spec.md",
)


class ActiveRuntimeBoundaryTests(unittest.TestCase):
    def test_removed_legacy_paths_are_not_tracked(self) -> None:
        tracked = subprocess.check_output(("git", "-C", str(ROOT), "ls-files"), text=True).splitlines()
        remaining = [
            path
            for path in tracked
            if any(path == removed or path.startswith(f"{removed}/") for removed in REMOVED_PATHS)
        ]
        self.assertFalse(remaining)

    def test_class1_readme_has_no_removed_entrypoints(self) -> None:
        text = (ROOT / "class_1_anomaly_detection" / "README.md").read_text(encoding="utf-8").lower()
        for token in ("run_graph_eda", "export_pyg_graph", "run_pygod_compare", "run_step4_evaluation", "streamlit run"):
            self.assertNotIn(token, text)

    def test_root_readme_links_to_supported_routes(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/data/local-analysis-turnkey-runbook.md", text)
        self.assertIn("tools/offline/analysis-kit/README.md", text)
        self.assertNotIn("class_2_supply_forecast", text)
        self.assertNotIn("streamlit", text.lower())

    def test_supported_runner_and_react_routes_exist(self) -> None:
        self.assertTrue((ROOT / "class_1_anomaly_detection" / "src" / "offline_anchor_runner.py").is_file())
        self.assertTrue((ROOT / "data_pipeline" / "offline" / "class2_analysis_export.py").is_file())
        self.assertTrue((ROOT / "web" / "class1_internal").is_dir())
        self.assertTrue((ROOT / "web" / "class2_public").is_dir())

    def test_active_execution_code_does_not_import_removed_runtime(self) -> None:
        pattern = re.compile(
            r"^\s*(?:from\s+(?:class_3_impact_evaluation|class_2_supply_forecast|shared_utils|class_1_anomaly_detection\.src\.(?:eda|experiments|graph|ingest))|import\s+(?:class_3_impact_evaluation|class_2_supply_forecast|shared_utils|class_1_anomaly_detection\.src\.(?:eda|experiments|graph|ingest)))",
            re.MULTILINE,
        )
        for suffix in ("*.py", "*.ps1"):
            for path in ROOT.rglob(suffix):
                if any(part in {".git", "node_modules", "__pycache__"} for part in path.parts):
                    continue
                self.assertIsNone(pattern.search(path.read_text(encoding="utf-8", errors="replace")), path.relative_to(ROOT).as_posix())

    def test_no_generated_or_data_artifacts_are_tracked(self) -> None:
        tracked = subprocess.check_output(("git", "-C", str(ROOT), "ls-files"), text=True).splitlines()
        forbidden = re.compile(r"(?i)(^|/)generated(/|$)|\.(xlsx|xls|parquet|sqlite|db|zip|exe|whl)$")
        self.assertFalse([path for path in tracked if forbidden.search(path)])
