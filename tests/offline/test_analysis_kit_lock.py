from pathlib import Path
import re
import unittest


class AnalysisKitLockTests(unittest.TestCase):
    def test_flat_lock_has_exact_hash_pins_and_api_closure_without_references(self):
        path = Path(__file__).parents[2] / "tools/offline/analysis-kit/requirements-analysis-kit-win-py313.lock"
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        pattern = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s#]+)\s+--hash=sha256:([0-9a-f]{64})(?:\s+#.*)?$")
        parsed = [pattern.fullmatch(line) for line in lines]
        self.assertEqual(len(lines), 55)
        self.assertTrue(all(parsed))
        self.assertEqual(len({match.group(1).lower().replace("_", "-") for match in parsed}), 55)
        self.assertTrue({"duckdb", "fastapi", "uvicorn"}.issubset({match.group(1).lower().replace("_", "-") for match in parsed}))
        self.assertFalse(any(re.search(r"(^|\s)-(r|c)\b|--(?:requirement|constraint)|://|(^|\s)-e\b", line) for line in lines))
