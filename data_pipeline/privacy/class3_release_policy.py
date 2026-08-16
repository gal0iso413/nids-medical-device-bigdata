"""Fail-closed Class 3 release-policy artifact builder; never a public release."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Literal

import pandas as pd
import pyarrow.parquet as pq

from data_pipeline.analysis.class3_serving_mart import (
    SERVING_MART_DATASET_NAME,
    SERVING_MART_SCHEMA_VERSION,
)
from data_pipeline.storage.monthly_fact_parquet import read_monthly_fact_partitions, verify_monthly_fact_partition

POLICY_VERSION = "1.0.0"
DATASET_NAME = "class3_release_policy"
STATUSES = frozenset({"not_approved", "candidate_released", "suppressed_small_cell", "suppressed_dominance", "suppressed_insufficient_coverage", "not_available"})

class ReleasePolicyError(RuntimeError): pass
class ReleasePolicyConflictError(ReleasePolicyError): pass

@dataclass(frozen=True)
class ReleasePolicyResult:
    status: Literal["written", "unchanged"]
    output_path: Path
    artifact_fingerprint: str

def _bytes(value: Any) -> bytes: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
def _hash(value: Any) -> str: return sha256(_bytes(value)).hexdigest()
def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""): digest.update(part)
    return digest.hexdigest()
def _inside(child: Path, parent: Path) -> bool:
    try: child.resolve().relative_to(parent.resolve()); return True
    except ValueError: return False
def _months(start: str, end: str) -> tuple[str, ...]:
    if not (isinstance(start, str) and isinstance(end, str) and len(start) == len(end) == 6 and start.isdigit() and end.isdigit()): raise ReleasePolicyError("period bounds must be YYYYMM")
    y, m, stop = int(start[:4]), int(start[4:]), (int(end[:4]), int(end[4:]))
    values: list[str] = []
    while (y, m) <= stop:
        if not 1 <= m <= 12: raise ReleasePolicyError("period bounds are invalid")
        values.append(f"{y:04d}{m:02d}"); y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    if not values: raise ReleasePolicyError("period order is invalid")
    return tuple(values)
def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes(); value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc: raise ReleasePolicyError("policy JSON is unreadable") from exc
    if not isinstance(value, dict) or raw != _bytes(value): raise ReleasePolicyError("policy JSON must be canonical")
    return value
def _load_policy(path: Path) -> dict[str, Any]:
    policy = _read_json(path)
    required = {"policy_version", "approval_status", "differencing_protection", "minimum_endpoint_count", "minimum_coverage_rate", "dominance_threshold"}
    if set(policy) != required or policy["policy_version"] != POLICY_VERSION: raise ReleasePolicyError("policy config fields are invalid")
    if policy["approval_status"] not in {"not_approved", "approved"} or policy["differencing_protection"] not in {"not_implemented", "implemented"}: raise ReleasePolicyError("policy approval state is invalid")
    if not isinstance(policy["minimum_endpoint_count"], int) or policy["minimum_endpoint_count"] < 1: raise ReleasePolicyError("minimum_endpoint_count is invalid")
    for key in ("minimum_coverage_rate", "dominance_threshold"):
        if not isinstance(policy[key], (int, float)) or not 0 <= policy[key] <= 1: raise ReleasePolicyError(f"{key} is invalid")
    return policy
def _mart_root(root: Path) -> Path:
    direct = root / "_manifest.json"
    return root if direct.is_file() else root / SERVING_MART_DATASET_NAME / f"schema_version={SERVING_MART_SCHEMA_VERSION}"
def _verified_mart(root: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    directory = _mart_root(root); manifest = _read_json(directory / "_manifest.json")
    fingerprint_keys = {
        "serving_mart_dataset_name", "serving_mart_schema_version", "fact_dataset_name",
        "fact_schema_version", "fact_schema_fingerprint", "period_start", "period_end",
        "source_partitions", "output_sha256",
    }
    if (
        manifest.get("serving_mart_dataset_name") != SERVING_MART_DATASET_NAME
        or manifest.get("serving_mart_schema_version") != SERVING_MART_SCHEMA_VERSION
        or set(manifest) != fingerprint_keys | {"created_fingerprint", "outputs"}
        or not isinstance(manifest.get("created_fingerprint"), str)
        or manifest["created_fingerprint"] != _hash({key: manifest[key] for key in fingerprint_keys})
    ):
        raise ReleasePolicyError("serving mart schema/fingerprint is invalid")
    expected_outputs = {
        "product_catalog", "product_month", "item_group_month", "endpoint_composition", "coverage",
    }
    all_files: dict[str, Path] = {}
    output_hashes: dict[str, str] = {}
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list): raise ReleasePolicyError("serving mart outputs are invalid")
    for output in outputs:
        if not isinstance(output, dict) or set(output) != {"name", "filename", "row_count", "sha256"} or output.get("name") not in expected_outputs: raise ReleasePolicyError("serving mart outputs are invalid")
        name, filename = output["name"], output["filename"]
        path = directory / str(filename)
        if (
            not isinstance(filename, str) or Path(filename).name != filename
            or not _inside(path, directory) or not path.is_file()
            or _file_hash(path) != output.get("sha256")
        ): raise ReleasePolicyError("serving mart output checksum/path is invalid")
        if not isinstance(output["row_count"], int) or output["row_count"] < 0 or pq.ParquetFile(path).metadata.num_rows != output["row_count"]: raise ReleasePolicyError("serving mart output row count is invalid")
        all_files[name] = path; output_hashes[name] = output["sha256"]
    if set(all_files) != expected_outputs or manifest["output_sha256"] != output_hashes: raise ReleasePolicyError("serving mart output checksum set is invalid")
    files = {name: all_files[name] for name in ("product_month", "item_group_month", "coverage")}
    return manifest, files
def _frame(path: Path) -> pd.DataFrame: return pq.read_table(path).to_pandas()
def _scope_rows(files: dict[str, Path], scope_type: str, scope_id: str, months: tuple[str, ...]) -> pd.DataFrame:
    name, column = ("product_month", "product_id") if scope_type == "product" else ("item_group_month", "item_group_id")
    data = _frame(files[name]); return data.loc[data["month"].isin(months) & data[column].eq(scope_id)].copy()
def _dominant(fact_root: Path, scope_type: str, scope_id: str, months: tuple[str, ...], threshold: float) -> bool:
    for month in months: verify_monthly_fact_partition(fact_root, month)
    fact = read_monthly_fact_partitions(fact_root, months=months)
    if scope_type == "product": scoped = fact.loc[fact["product_id"].eq(scope_id)]
    else: scoped = fact.loc[fact["item_group_id"].eq(scope_id)]
    amounts = scoped.groupby("src_company_id", dropna=False)["amount_sum_clean"].sum(min_count=1).dropna()
    total = sum(amounts, start=0)
    return bool(amounts.size and total and max(amounts) / total >= threshold)
def _status(policy: dict[str, Any], rows: pd.DataFrame, fact_root: Path | None, scope_type: str, scope_id: str, months: tuple[str, ...]) -> str:
    if policy["approval_status"] != "approved": return "not_approved"
    if rows.empty: return "not_available"
    if int(rows[["supplier_count_distinct", "receiver_count_distinct"]].min().min()) < policy["minimum_endpoint_count"]: return "suppressed_small_cell"
    coverage = rows["amount_valid_row_count"].sum() / max(rows["tx_count"].sum(), 1)
    if coverage < policy["minimum_coverage_rate"]: return "suppressed_insufficient_coverage"
    if fact_root is not None and _dominant(fact_root, scope_type, scope_id, months, policy["dominance_threshold"]): return "suppressed_dominance"
    if policy["differencing_protection"] != "implemented": return "not_approved"
    return "candidate_released"
def evaluate_class3_release_policy(*, mart_root: Path, policy_config: Path, output_root: Path, period_start: str, period_end: str, scopes: tuple[tuple[str, str], ...], fact_root: Path | None = None, checkpoint_root: Path | None = None) -> ReleasePolicyResult:
    for root in (mart_root, fact_root, checkpoint_root):
        if root is not None and (_inside(output_root, root) or _inside(root, output_root)): raise ReleasePolicyError("output_root must not overlap source or checkpoint root")
    policy = _load_policy(policy_config); months = _months(period_start, period_end); mart_manifest, files = _verified_mart(mart_root)
    if not scopes or any(kind not in {"product", "item_group"} or not value for kind, value in scopes): raise ReleasePolicyError("scopes are invalid")
    entries = []
    for kind, value in sorted(set(scopes)):
        state = _status(policy, _scope_rows(files, kind, value, months), fact_root, kind, value, months)
        entries.append({"scope_type": kind, "scope_id": value, "period_start": period_start, "period_end": period_end, "metric_family": "endpoint_and_coverage", "status": state, "policy_version": POLICY_VERSION, "coverage_summary": "evaluated"})
    artifact_input = {"policy": policy, "policy_config_sha256": _file_hash(policy_config), "mart_fingerprint": mart_manifest["created_fingerprint"], "period_start": period_start, "period_end": period_end, "fact_checksums_verified": fact_root is not None, "differencing_attack_protection": policy["differencing_protection"], "entries": entries}
    artifact = {**artifact_input, "artifact_fingerprint": _hash(artifact_input)}; data = _bytes(artifact); final = output_root / DATASET_NAME / f"schema_version={POLICY_VERSION}"; manifest = {"dataset_name": DATASET_NAME, "policy_version": POLICY_VERSION, "artifact_filename": "release-status.json", "artifact_sha256": sha256(data).hexdigest(), "artifact_fingerprint": artifact["artifact_fingerprint"]}; manifest_data = _bytes(manifest)
    final.parent.mkdir(parents=True, exist_ok=True); stage = Path(tempfile.mkdtemp(prefix=f".{final.name}.tmp-", dir=final.parent))
    try:
        (stage / "release-status.json").write_bytes(data); (stage / "_manifest.json").write_bytes(manifest_data)
        if final.exists():
            if (final / "_manifest.json").read_bytes() == manifest_data and (final / "release-status.json").read_bytes() == data: return ReleasePolicyResult("unchanged", final, artifact["artifact_fingerprint"])
            raise ReleasePolicyConflictError("release policy output already exists with different content")
        os.replace(stage, final); return ReleasePolicyResult("written", final, artifact["artifact_fingerprint"])
    finally:
        if stage.exists(): shutil.rmtree(stage)
