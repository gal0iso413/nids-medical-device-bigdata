"""
Pack a minimal onsite visit zip for Class 1.

Run from repo root:
  python onsite_kit/pack_onsite_zip.py
"""
from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "onsite_kit"
STAMP = date.today().strftime("%Y%m%d")
ZIP_PATH = OUT_DIR / f"nids_class1_onsite_kit_{STAMP}.zip"

# (repo-relative path, arcname inside zip)
INCLUDE_FILES = [
    "requirements.txt",
    "shared_data/DATA_LAYER.md",
    "shared_docs/official/description_master_registration.md",
    "shared_docs/official/description_transaction_supply.md",
    "shared_docs/official/medical_device_bigdata_spec.md",
    "shared_docs/structured/class_1_anomaly_spec.md",
    "shared_docs/structured/onsite_visit1_summary.md",
    "shared_utils/slacker.py",
    "shared_utils/README.md",
    "class_1_anomaly_detection/README.md",
    "class_1_anomaly_detection/requirements-ml.txt",
    "class_1_anomaly_detection/app.py",
    "class_1_anomaly_detection/.env.example",
    "onsite_kit/ONSITE_RUNBOOK.md",
    "onsite_kit/setup_venv.ps1",
]

INCLUDE_GLOBS = [
    "class_1_anomaly_detection/src/**/*.py",
    "class_1_anomaly_detection/exports/**/*",
    "class_1_anomaly_detection/tests/**/*.py",
]

SKIP_PARTS = {
    "__pycache__",
    ".pytest_cache",
    "output",
    "data",
    ".env",
}


def _iter_paths() -> list[Path]:
    paths: list[Path] = []
    for rel in INCLUDE_FILES:
        p = REPO / rel
        if p.is_file():
            paths.append(p)
    for pattern in INCLUDE_GLOBS:
        for p in REPO.glob(pattern):
            if not p.is_file():
                continue
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            paths.append(p)
    # stable unique
    return sorted(set(paths), key=lambda x: str(x).lower())


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = _iter_paths()
    # Place runbook at zip root for visibility
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README_FIRST.txt",
            "Open onsite_kit/ONSITE_RUNBOOK.md first.\n"
            "Extract so that class_1_anomaly_detection/ is at the kit root.\n",
        )
        for p in files:
            arc = p.relative_to(REPO).as_posix()
            zf.write(p, arcname=arc)
        # empty placeholders
        zf.writestr("shared_data/.gitkeep", "")
        zf.writestr("class_1_anomaly_detection/data/.gitkeep", "")
        zf.writestr("class_1_anomaly_detection/output/.gitkeep", "")

    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"Wrote {ZIP_PATH} ({size_mb:.2f} MB, {len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
