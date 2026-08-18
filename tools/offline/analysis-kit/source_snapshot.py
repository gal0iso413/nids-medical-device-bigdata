"""Deterministic, allowlisted working-tree source snapshots for analysis kits."""
from __future__ import annotations
import hashlib, json, shutil, subprocess
from pathlib import Path, PurePosixPath

ALLOWED_UNTRACKED = (
    "tools/offline/analysis-kit/",
    "config/class1-graph-scale-gate.example.json",
    "data_pipeline/analysis/class1_lookup_index.py",
    "data_pipeline/ingest/company_display_name.py",
    "data_pipeline/observability/class1_graph_scale_gate.py",
    "docs/data/offline-analysis-python-environment.md",
    "docs/data/class1-graph-scale-gate.md",
    "docs/data/company-display-name.md",
    "docs/service/class3-local-integrated-host.md",
    "docs/service/class1-local-query-api.md",
    "docs/service/class1-local-integrated-host.md",
    "services/class1_local_api/",
    "tests/offline/",
    "tests/services/",
    "tests/analysis/",
    "tests/ingest/",
    "tests/observability/",
)
TRACKED_ROOTS = ("data_pipeline/", "class_1_anomaly_detection/", "services/class1_local_api/", "services/class3_local_api/", "tools/offline/analysis-kit/", "config/", "tests/", "docs/data/", "docs/service/", "requirements-data-pipeline.txt", "README.md")
FORBIDDEN_SUFFIXES = {".xlsx", ".xls", ".xlsm", ".parquet", ".sqlite", ".whl", ".zip", ".exe"}
FORBIDDEN_PARTS = {".git", "node_modules", "dist", "generated", "checkpoint", "checkpoints", "output", "__pycache__"}

def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
def _git(root: Path, *args: str) -> list[str]: return subprocess.check_output(("git", "-C", str(root), *args), text=True).splitlines()
def _safe(relative: str) -> PurePosixPath:
    path=PurePosixPath(relative)
    blocked = any(part in FORBIDDEN_PARTS - {"checkpoint", "checkpoints"} for part in path.parts) or (any(part in {"checkpoint", "checkpoints"} for part in path.parts) and path.suffix.lower() not in {".py", ".md"})
    if not relative or path.is_absolute() or ".." in path.parts or blocked or path.suffix.lower() in FORBIDDEN_SUFFIXES or any(part.startswith(".env") for part in path.parts): raise ValueError(f"forbidden source snapshot path: {relative}")
    return path
def _allowed(path: str) -> bool: return any(path == item or path.startswith(item) for item in ALLOWED_UNTRACKED)
def _entry(root: Path, relative: str) -> dict:
    source=root.joinpath(*_safe(relative).parts)
    if not source.is_file() or source.is_symlink(): raise ValueError(f"snapshot source is not a regular file: {relative}")
    data=source.read_bytes(); return {"relative_path":relative,"size":len(data),"sha256":hashlib.sha256(data).hexdigest()}

def create_snapshot(root: Path, staging: Path) -> dict:
    root=root.resolve(); staging=staging.resolve()
    if staging.exists(): raise ValueError("snapshot staging directory must not exist")
    tracked=sorted(path for path in _git(root,"ls-files") if any(path == item or path.startswith(item) for item in TRACKED_ROOTS) and not any(part.startswith(".env") for part in PurePosixPath(path).parts)); untracked=sorted(_git(root,"ls-files","--others","--exclude-standard")); allowed=sorted(path for path in untracked if _allowed(path))
    paths=sorted(set(tracked+allowed)); entries=[_entry(root,path) for path in paths]
    try:
        staging.mkdir(parents=True)
        for entry in entries:
            target=staging.joinpath(*PurePosixPath(entry["relative_path"]).parts); target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(root/entry["relative_path"],target)
        dirty=sorted(set(_git(root,"diff","--name-only")+_git(root,"diff","--name-only","--cached")))
        manifest={"base_commit_sha":_git(root,"rev-parse","HEAD")[0],"source_mode":"working-tree","files":entries,"source_tree_fingerprint":hashlib.sha256(canonical(entries)).hexdigest(),"dirty_tracked_paths":dirty,"allowed_untracked_paths":allowed,"file_count":len(entries)}
        (staging/"source-snapshot-manifest.json").write_bytes(canonical(manifest)+b"\n"); return manifest
    except Exception:
        shutil.rmtree(staging,ignore_errors=True); raise

if __name__ == "__main__":
    import sys; print(canonical(create_snapshot(Path(sys.argv[1]),Path(sys.argv[2]))).decode())
