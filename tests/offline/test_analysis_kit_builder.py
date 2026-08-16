import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


REPOSITORY_ROOT = Path(__file__).parents[2]
SCRIPT_SOURCE = REPOSITORY_ROOT / "tools" / "offline" / "analysis-kit"


class AnalysisKitBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT)
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.script_root = self.repository / "tools" / "offline" / "analysis-kit"
        shutil.copytree(SCRIPT_SOURCE, self.script_root, ignore=shutil.ignore_patterns("__pycache__"))
        self.wheelhouse = self.root / "wheelhouse"
        self.class1 = self.root / "class1-dist"
        self.class3 = self.root / "class3-dist"
        self.wheelhouse.mkdir()
        for dist, marker in ((self.class1, b"class1"), (self.class3, b"class3")):
            (dist / "assets").mkdir(parents=True)
            (dist / "index.html").write_bytes(b"<html></html>\n")
            (dist / "assets" / "app.js").write_bytes(marker)

        lock_lines = []
        for index in range(43):
            package = f"package{index:02d}"
            wheel = self.wheelhouse / f"{package}-1.0.0-py3-none-any.whl"
            wheel.write_bytes(f"synthetic-wheel-{index}\n".encode())
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            lock_lines.append(f"{package}==1.0.0 --hash=sha256:{digest}")
        (self.script_root / "requirements-analysis-kit-win-py313.lock").write_text(
            "\n".join(lock_lines) + "\n", encoding="utf-8"
        )

        self.installer = self.root / "python-installer.exe"
        self.installer.write_bytes(b"synthetic installer")
        installer_hash = hashlib.sha256(self.installer.read_bytes()).hexdigest()
        common = self.script_root / "analysis-kit-common.ps1"
        common.write_text(
            common.read_text(encoding="utf-8").replace(
                "96159fcb523ae404b707186a75b4104ee23851e476a5e838e14584cf1e03f981",
                installer_hash,
            ),
            encoding="utf-8",
        )

        (self.repository / "snapshot-input.txt").write_text("snapshot\n", encoding="utf-8")
        (self.script_root / "source_snapshot.py").write_text(
            """import hashlib, json, pathlib, shutil, sys
root, staging = map(pathlib.Path, sys.argv[1:3])
staging.mkdir(parents=True)
data = (root / 'snapshot-input.txt').read_bytes()
(staging / 'snapshot-input.txt').write_bytes(data)
entries = [{'relative_path':'snapshot-input.txt','size':len(data),'sha256':hashlib.sha256(data).hexdigest()}]
manifest = {'base_commit_sha':'a'*40,'source_mode':'working-tree','files':entries,'source_tree_fingerprint':hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'dirty_tracked_paths':[],'allowed_untracked_paths':[],'file_count':1}
(staging / 'source-snapshot-manifest.json').write_text(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\\n',encoding='utf-8')
""",
            encoding="utf-8",
        )
        self.output = self.root / "published-kit"

    def tearDown(self):
        self.temporary.cleanup()

    def build(self, *, output=None, wheelhouse=None, class1=None, class3=None):
        command = [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(self.script_root / "build-analysis-kit.ps1"),
            "-PythonExe", sys.executable,
            "-PythonInstaller", str(self.installer),
            "-WheelhouseDirectory", str(wheelhouse or self.wheelhouse),
            "-Class1DistDirectory", str(class1 or self.class1),
            "-Class3DistDirectory", str(class3 or self.class3),
            "-OutputDirectory", str(output or self.output),
        ]
        return subprocess.run(command, text=True, capture_output=True, encoding="utf-8")

    def test_build_is_exact_safe_atomic_idempotent_and_cleans_failures(self):
        first = self.build()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(json.loads(first.stdout.strip().splitlines()[-1])["status"], "built")
        self.assertEqual(list(self.root.glob(".analysis-kit.tmp-*")), [])

        manifest_path = self.output / "analysis-kit-manifest.json"
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
        self.assertEqual(
            manifest_text,
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n",
        )
        manifest_paths = [entry["relative_path"] for entry in manifest["files"]]
        self.assertEqual(manifest_paths, sorted(manifest_paths, key=str.lower))
        declared = {entry["relative_path"] for entry in manifest["files"]}
        actual = {
            path.relative_to(self.output).as_posix()
            for path in self.output.rglob("*")
            if path.is_file() and path.name != "analysis-kit-manifest.json"
        }
        self.assertEqual(declared, actual)
        built_wheels = sorted((self.output / "wheels").glob("*.whl"))
        input_wheels = sorted(self.wheelhouse.glob("*.whl"))
        self.assertEqual(len(built_wheels), 43)
        self.assertEqual(
            [(path.name, hashlib.sha256(path.read_bytes()).hexdigest()) for path in built_wheels],
            [(path.name, hashlib.sha256(path.read_bytes()).hexdigest()) for path in input_wheels],
        )
        self.assertEqual(
            len([entry for entry in manifest["files"] if entry["role"] == "wheel"]), 43
        )

        archive_path = self.output / manifest["source_snapshot"]["archive"]
        snapshot_manifest_path = self.output / manifest["source_snapshot"]["manifest"]
        self.assertTrue(archive_path.is_file())
        self.assertTrue(snapshot_manifest_path.is_file())
        with zipfile.ZipFile(archive_path) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"snapshot-input.txt", "source-snapshot-manifest.json"},
            )
            self.assertEqual(
                archive.read("source-snapshot-manifest.json"),
                snapshot_manifest_path.read_bytes(),
            )

        for site, source in (("class1", self.class1), ("class3", self.class3)):
            site_root = self.output / "sites" / site
            self.assertEqual((site_root / "index.html").read_bytes(), (source / "index.html").read_bytes())
            self.assertEqual((site_root / "assets" / "app.js").read_bytes(), (source / "assets" / "app.js").read_bytes())
            generated = self.output / "sites" / site / "generated"
            self.assertTrue(generated.is_dir())
            self.assertEqual(list(generated.iterdir()), [])

        manifest_bytes = manifest_path.read_bytes()
        second = self.build()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(json.loads(second.stdout.strip().splitlines()[-1])["status"], "unchanged")
        self.assertEqual(manifest_path.read_bytes(), manifest_bytes)
        self.assertEqual(list(self.root.glob(".analysis-kit.tmp-*")), [])

        (self.class1 / "assets" / "app.js").write_bytes(b"different class1")
        conflict = self.build()
        self.assertNotEqual(conflict.returncode, 0)
        self.assertIn("different analysis kit", conflict.stderr)
        self.assertEqual(manifest_path.read_bytes(), manifest_bytes)
        self.assertEqual(list(self.root.glob(".analysis-kit.tmp-*")), [])

        for index, blocked_name in enumerate(
            ("raw-score.json", "restricted-qa.json", "source-snapshot-manifest.json")
        ):
            with self.subTest(blocked_static_artifact=blocked_name):
                unsafe_dist = self.root / f"unsafe-dist-{index}"
                shutil.copytree(self.class1, unsafe_dist)
                (unsafe_dist / blocked_name).write_text("{}", encoding="utf-8")
                failed_output = self.root / f"failed-kit-{index}"
                failed = self.build(output=failed_output, class1=unsafe_dist)
                self.assertNotEqual(failed.returncode, 0)
                self.assertIn("raw-score, QA, or source-manifest", failed.stderr)
                self.assertFalse(failed_output.exists())
                self.assertEqual(list(self.root.glob(".analysis-kit.tmp-*")), [])

    def test_rejects_wheel_whose_hash_and_filename_identity_do_not_belong_together(self):
        identity = self.root / "wheelhouse-identity-mismatch"
        missing = self.root / "wheelhouse-missing"
        extra = self.root / "wheelhouse-extra"
        sha_mismatch = self.root / "wheelhouse-sha-mismatch"
        for case in (identity, missing, extra, sha_mismatch):
            shutil.copytree(self.wheelhouse, case)

        first, second = sorted(identity.glob("*.whl"))[:2]
        first_bytes, second_bytes = first.read_bytes(), second.read_bytes()
        first.write_bytes(second_bytes)
        second.write_bytes(first_bytes)
        next(iter(missing.glob("*.whl"))).unlink()
        (extra / "unexpected-1.0.0-py3-none-any.whl").write_bytes(b"extra wheel")
        next(iter(sha_mismatch.glob("*.whl"))).write_bytes(b"tampered wheel")

        cases = (
            ("identity", identity, "package/version does not match"),
            ("missing", missing, "exactly match the locked wheel count"),
            ("extra", extra, "exactly match the locked wheel count"),
            ("sha", sha_mismatch, "not present in the locked hash set"),
        )
        for name, wheelhouse, expected_error in cases:
            with self.subTest(wheelhouse_case=name):
                output = self.root / f"rejected-{name}"
                result = self.build(output=output, wheelhouse=wheelhouse)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(list(self.root.glob(".analysis-kit.tmp-*")), [])


if __name__ == "__main__":
    unittest.main()
