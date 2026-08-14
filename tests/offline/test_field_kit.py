from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from uuid import uuid4


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPOSITORY_ROOT / "tools" / "offline"
LOCK = TOOLS / "requirements-field-kit-win-py313.lock"
SCRIPTS = (
    "field-kit-common.ps1",
    "build-field-kit.ps1",
    "verify-field-kit.ps1",
    "install-field-env.ps1",
    "smoke-test.ps1",
)
EXPECTED_PACKAGES = {
    "numpy": "2.4.6",
    "pandas": "3.0.3",
    "pyarrow": "24.0.0",
    "openpyxl": "3.1.5",
    "et-xmlfile": "2.0.0",
    "python-dateutil": "2.9.0.post0",
    "six": "1.17.0",
    "tzdata": "2026.2",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class OfflineFieldKitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = REPOSITORY_ROOT / f".offline-field-kit-test-{uuid4().hex}"
        self.temp.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def _synthetic_kit(self) -> Path:
        kit = self.temp / "한글 공간 kit"
        kit.mkdir()
        for name in (
            "field-kit-common.ps1",
            "verify-field-kit.ps1",
            "install-field-env.ps1",
            "smoke-test.ps1",
        ):
            shutil.copy2(TOOLS / name, kit / name)
        payload = kit / "payload" / "synthetic.txt"
        payload.parent.mkdir()
        payload.write_text("synthetic only\n", encoding="utf-8")
        lock = kit / "metadata" / "requirements-field-kit-win-py313.lock"
        lock.parent.mkdir()
        lock.write_text("synthetic==1 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
        entries = []
        for path in sorted(p for p in kit.rglob("*") if p.is_file()):
            entries.append(
                {
                    "relative_path": path.relative_to(kit).as_posix(),
                    "role": "test",
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
        manifest = {
            "contract_version": "1.0.0",
            "source_commit": "a" * 40,
            "python": {
                "implementation": "CPython",
                "version": "3.13.12",
                "major_minor": "3.13",
                "architecture": "64bit",
                "platform": "win_amd64",
                "installer_sha256": "96159fcb523ae404b707186a75b4104ee23851e476a5e838e14584cf1e03f981",
            },
            "dependency_lock": "metadata/requirements-field-kit-win-py313.lock",
            "source_snapshot_policy": "synthetic test",
            "files": entries,
        }
        (kit / "field-kit-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return kit

    def _verify(self, kit: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(kit / "verify-field-kit.ps1"),
                "-KitDirectory",
                str(kit),
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )

    def _run_from_other_cwd(
        self,
        kit: Path,
        script_name: str,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        other_cwd = self.temp / "다른 작업 폴더"
        other_cwd.mkdir(exist_ok=True)
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(kit / script_name),
                *arguments,
            ],
            cwd=other_cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )

    def test_lock_is_exact_hash_pinned_and_complete(self) -> None:
        packages: dict[str, str] = {}
        for raw in LOCK.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            requirement, hash_option = line.split(" --hash=sha256:")
            name, version = requirement.split("==")
            self.assertRegex(hash_option, r"^[0-9a-f]{64}$")
            packages[name] = version
        self.assertEqual(packages, EXPECTED_PACKAGES)

    def test_lock_contains_no_url_range_or_source_artifact(self) -> None:
        text = LOCK.read_text(encoding="utf-8")
        for forbidden in ("http://", "https://", ">=", "<=", "~=", ".tar.gz", ".zip"):
            self.assertNotIn(forbidden, text)

    def test_powershell_scripts_parse_without_syntax_errors(self) -> None:
        for name in SCRIPTS:
            with self.subTest(script=name):
                path = str(TOOLS / name).replace("'", "''")
                command = (
                    "$tokens=$null; $errors=$null; "
                    f"[System.Management.Automation.Language.Parser]::ParseFile('{path}',"
                    "[ref]$tokens,[ref]$errors) | Out-Null; "
                    "if($errors.Count -ne 0){$errors | ForEach-Object {$_.ToString()}; exit 1}"
                )
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command", command],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_verifier_accepts_exact_synthetic_kit_with_unicode_and_spaces(self) -> None:
        result = self._verify(self._synthetic_kit())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "verified")

    def test_verify_defaults_to_script_directory_from_other_cwd(self) -> None:
        kit = self._synthetic_kit()
        result = self._run_from_other_cwd(kit, "verify-field-kit.ps1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "verified")

    def test_install_defaults_to_script_directory_from_other_cwd(self) -> None:
        kit = self._synthetic_kit()
        missing_python = self.temp / "missing python.exe"
        result = self._run_from_other_cwd(
            kit,
            "install-field-env.ps1",
            "-PythonExe",
            str(missing_python),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python executable does not exist", result.stderr)
        self.assertNotIn("manifest.json is missing", result.stderr)

    def test_smoke_defaults_to_script_directory_from_other_cwd(self) -> None:
        kit = self._synthetic_kit()
        result = self._run_from_other_cwd(kit, "smoke-test.ps1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Installed field environment is incomplete", result.stderr)
        self.assertNotIn("manifest.json is missing", result.stderr)

    def test_verifier_blocks_missing_file(self) -> None:
        kit = self._synthetic_kit()
        (kit / "payload" / "synthetic.txt").unlink()
        result = self._verify(kit)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("file set mismatch", result.stderr)

    def test_verifier_blocks_additional_file(self) -> None:
        kit = self._synthetic_kit()
        (kit / "unexpected.bin").write_bytes(b"unexpected")
        result = self._verify(kit)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("file set mismatch", result.stderr)

    def test_verifier_blocks_nested_manifest_named_as_root_manifest(self) -> None:
        kit = self._synthetic_kit()
        nested = kit / "unexpected" / "field-kit-manifest.json"
        nested.parent.mkdir()
        nested.write_text("{}", encoding="utf-8")
        result = self._verify(kit)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("file set mismatch", result.stderr)

    def test_verifier_blocks_modified_file(self) -> None:
        kit = self._synthetic_kit()
        (kit / "payload" / "synthetic.txt").write_text("changed", encoding="utf-8")
        result = self._verify(kit)
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr, r"(size|checksum) mismatch")

    def test_builder_requires_clean_tree_and_external_output(self) -> None:
        text = (TOOLS / "build-field-kit.ps1").read_text(encoding="utf-8")
        self.assertIn("status --porcelain=v1 --untracked-files=all", text)
        self.assertIn("OutputDirectory must be outside the Git repository", text)
        self.assertNotIn("--no-check-certificate", text)

    def test_builder_uses_binary_only_hash_locked_download(self) -> None:
        text = (TOOLS / "build-field-kit.ps1").read_text(encoding="utf-8")
        for option in ("--require-hashes", "--only-binary=:all:", "--no-deps", "--platform win_amd64", "--abi cp313"):
            self.assertIn(option, text)

    def test_source_snapshot_is_allowlisted_and_excludes_runtime_artifacts(self) -> None:
        text = (TOOLS / "build-field-kit.ps1").read_text(encoding="utf-8")
        for included in ('"data_pipeline"', '"config/field-run.example.toml"', '"tests"', '"docs/data"'):
            self.assertIn(included, text)
        for forbidden in ("node_modules", "parquet", "sqlite", "field-run"):
            self.assertIn(forbidden, text)

    def test_installer_is_no_index_binary_only_and_clean_target(self) -> None:
        text = (TOOLS / "install-field-env.ps1").read_text(encoding="utf-8")
        for required in ("--no-index", "--find-links", "--only-binary=:all:", "--require-hashes"):
            self.assertIn(required, text)
        self.assertIn("InstallDirectory must not exist", text)
        self.assertNotRegex(text, r"(?i)Start-Process.+python-3\.13\.12-amd64")

    def test_smoke_test_is_synthetic_and_disables_pip_index(self) -> None:
        text = (TOOLS / "smoke-test.ps1").read_text(encoding="utf-8")
        self.assertIn('PIP_NO_INDEX = "1"', text)
        self.assertIn("tests.cli.test_field_runner", text)
        self.assertIn('actual_data_read = $false', text)
        self.assertIn('network_access = "not_attempted"', text)


if __name__ == "__main__":
    unittest.main()
