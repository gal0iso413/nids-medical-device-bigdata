"""Safely run the Class 1 GAD-NR contract from verified local partitions.

This module is deliberately an offline, internal-only publisher.  It reads no
raw source workbooks, starts no service, and only publishes under an explicitly
configured ignored output root.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Final, Sequence

import pandas as pd

from class_1_anomaly_detection.src.model_pipeline import (
    FEATURE_VERSION,
    PIPELINE_SCHEMA_VERSION,
    build_class1_pipeline,
    build_gadnr_features,
    build_model_graph,
    serialize_service_results,
)
from data_pipeline.contracts.supply_monthly import FACT_SCHEMA_VERSION
from data_pipeline.storage.monthly_fact_parquet import (
    PartitionVerification,
    read_monthly_fact_partitions,
    verify_monthly_fact_partition,
)


RUNNER_SCHEMA_VERSION: Final = "1.0.0"
QA_FILENAME: Final = "restricted-qa.json"
SERVICE_FILENAME: Final = "internal-service.json"
MANIFEST_FILENAME: Final = "run-manifest.json"


class Class1OfflineAnchorRunError(RuntimeError):
    """Raised when an internal anchor run cannot be completed safely."""


class Class1OfflineAnchorRunConflictError(Class1OfflineAnchorRunError):
    """Raised instead of replacing an existing non-identical run."""


@dataclass(frozen=True)
class Class1OfflineAnchorConfig:
    parquet_root: Path
    output_root: Path
    anchor_month: str
    region_vocabulary: tuple[str, ...]
    model_version: str
    seed: int
    minimum_role_sample: int
    minimum_node_count: int = 2
    minimum_edge_count: int = 1


@dataclass(frozen=True)
class Class1OfflineAnchorRunResult:
    status: str
    run_status: str
    run_directory: Path
    manifest_path: Path
    run_fingerprint: str


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return sha256(_canonical_json_bytes(value)).hexdigest()


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "as_tuple"):  # Decimal, without importing private pipeline helpers.
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, bool):
        return value
    if hasattr(value, "item"):
        try:
            return _json_value(value.item())
        except ValueError:
            pass
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _months(anchor_month: str) -> tuple[str, ...]:
    try:
        anchor = pd.Period(anchor_month, freq="M")
    except (TypeError, ValueError) as exc:
        raise Class1OfflineAnchorRunError("anchor_month must be YYYYMM") from exc
    if anchor.strftime("%Y%m") != anchor_month:
        raise Class1OfflineAnchorRunError("anchor_month must be YYYYMM")
    return tuple((anchor - offset).strftime("%Y%m") for offset in reversed(range(6)))


def _paths_overlap(first: Path, second: Path) -> bool:
    first_resolved = first.resolve(strict=False)
    second_resolved = second.resolve(strict=False)
    try:
        first_resolved.relative_to(second_resolved)
        return True
    except ValueError:
        try:
            second_resolved.relative_to(first_resolved)
            return True
        except ValueError:
            return False


def _validate_config(config: Class1OfflineAnchorConfig) -> tuple[str, ...]:
    months = _months(config.anchor_month)
    if _paths_overlap(config.parquet_root, config.output_root):
        raise Class1OfflineAnchorRunError("output_root and parquet_root must be distinct and non-nested")
    if not config.region_vocabulary:
        raise Class1OfflineAnchorRunError("region_vocabulary must be explicitly configured and non-empty")
    if tuple(sorted(set(config.region_vocabulary))) != config.region_vocabulary:
        raise Class1OfflineAnchorRunError("region_vocabulary must be sorted and unique")
    if not config.model_version.strip():
        raise Class1OfflineAnchorRunError("model_version is required")
    if config.minimum_role_sample < 1 or config.minimum_node_count < 1 or config.minimum_edge_count < 1:
        raise Class1OfflineAnchorRunError("minimum sample and graph thresholds must be positive")
    return months


def _lineage_item(item: PartitionVerification) -> dict[str, Any]:
    return {
        "month": item.month,
        "row_count": item.row_count,
        "relative_parquet_path": item.relative_parquet_path,
        "parquet_sha256": item.parquet_sha256,
        "parquet_file_size": item.parquet_file_size,
    }


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise Class1OfflineAnchorRunError(f"could not atomically publish {path.name}") from exc


def _existing_status(
    *, qa_path: Path, service_path: Path, manifest_path: Path, run_fingerprint: str,
    qa_sha256: str, service_sha256: str,
) -> str | None:
    existing = (qa_path.exists(), service_path.exists(), manifest_path.exists())
    if not any(existing):
        return None
    if existing == (True, True, False):
        if sha256(qa_path.read_bytes()).hexdigest() == qa_sha256 and sha256(service_path.read_bytes()).hexdigest() == service_sha256:
            return "recover"
        raise Class1OfflineAnchorRunConflictError("existing partial payload differs; refusing overwrite")
    if existing != (True, True, True):
        raise Class1OfflineAnchorRunConflictError("existing run is incomplete; refusing overwrite")
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Class1OfflineAnchorRunConflictError("existing run manifest is unreadable; refusing overwrite") from exc
    if manifest_bytes != _canonical_json_bytes(manifest):
        raise Class1OfflineAnchorRunConflictError("existing run manifest is not canonical; refusing overwrite")
    if (manifest.get("run_fingerprint") != run_fingerprint
            or manifest.get("output_sha256") != {QA_FILENAME: qa_sha256, SERVICE_FILENAME: service_sha256}
            or sha256(qa_path.read_bytes()).hexdigest() != qa_sha256
            or sha256(service_path.read_bytes()).hexdigest() != service_sha256):
        raise Class1OfflineAnchorRunConflictError("existing run has different lineage, settings, or content; refusing overwrite")
    return "unchanged"


def _insufficient_payload(config: Class1OfflineAnchorConfig, graph: Any, features: pd.DataFrame, feature_manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    reason = "minimum_node_count" if len(graph.nodes) < config.minimum_node_count else "minimum_edge_count"
    graph_summary = {"node_count": len(graph.nodes), "edge_count": len(graph.edges), "self_loop_count": graph.self_loop_count}
    shared = {"analysis_schema_version": PIPELINE_SCHEMA_VERSION, "run_status": "insufficient_graph", "reason": reason}
    qa = {**shared, "qa_results": [], "graph_summary": graph_summary, "feature_fingerprint": feature_manifest["feature_fingerprint"]}
    service = {**shared, "service_results": serialize_service_results(pd.DataFrame()), "graph_summary": graph_summary}
    return qa, service


def run_class1_offline_anchor(
    config: Class1OfflineAnchorConfig,
    *,
    scorer: Callable[[pd.DataFrame, tuple[tuple[int, ...], tuple[int, ...]]], list[float]] | None = None,
) -> Class1OfflineAnchorRunResult:
    """Verify six partitions, run GAD-NR when viable, and publish immutable local artifacts."""
    months = _validate_config(config)
    try:
        verifications = tuple(verify_monthly_fact_partition(config.parquet_root, month) for month in months)
        fact = read_monthly_fact_partitions(config.parquet_root, months=months)
    except Exception as exc:
        raise Class1OfflineAnchorRunError("all six required monthly partitions must exist and pass checksum verification") from exc
    lineage = [_lineage_item(item) for item in verifications]
    source_versions = tuple(sorted(fact["source_version"].dropna().astype(str).unique()))
    graph = build_model_graph(fact, anchor_month=config.anchor_month)
    if len(graph.nodes) < config.minimum_node_count or len(graph.edges) < config.minimum_edge_count:
        features, feature_manifest = build_gadnr_features(fact, graph, region_vocabulary=config.region_vocabulary)
        qa_payload, service_payload = _insufficient_payload(config, graph, features, feature_manifest)
        run_status = "insufficient_graph"
        pipeline_manifest = {
            "feature_version": FEATURE_VERSION,
            "feature_fingerprint": feature_manifest["feature_fingerprint"],
            "graph_summary": {"node_count": len(graph.nodes), "edge_count": len(graph.edges), "self_loop_count": graph.self_loop_count},
            "graph_fingerprint": _fingerprint({
                "nodes": graph.nodes, "edges": graph.edges.to_dict("records"),
                "window_months": graph.window_months,
            }),
        }
        pipeline_manifest["manifest_fingerprint"] = _fingerprint(pipeline_manifest)
    else:
        try:
            result = build_class1_pipeline(
                fact, anchor_month=config.anchor_month, model_version=config.model_version,
                scorer=scorer, seed=config.seed, minimum_role_sample=config.minimum_role_sample,
                region_vocabulary=config.region_vocabulary,
            )
        except RuntimeError as exc:
            if "optional" in str(exc).casefold() or "pygod" in str(exc).casefold():
                raise Class1OfflineAnchorRunError(f"optional ML dependency unavailable: {exc}") from exc
            raise
        qa_payload = _json_value({
            "analysis_schema_version": PIPELINE_SCHEMA_VERSION, "run_status": "completed",
            "qa_results": result.qa_results.to_dict("records"),
            "previous_anchor_diff": result.previous_anchor_diff,
            "prior_nonoverlap_3m_diff": result.prior_nonoverlap_3m_diff,
            "bc_evidence": result.bc_evidence,
        })
        service_payload = _json_value({
            "analysis_schema_version": PIPELINE_SCHEMA_VERSION, "run_status": "completed",
            "service_results": serialize_service_results(result.service_results),
        })
        run_status = "completed"
        pipeline_manifest = result.manifest
    qa_bytes = _canonical_json_bytes(qa_payload)
    service_bytes = _canonical_json_bytes(service_payload)
    output_sha256 = {QA_FILENAME: sha256(qa_bytes).hexdigest(), SERVICE_FILENAME: sha256(service_bytes).hexdigest()}
    run_input = {
        "runner_schema_version": RUNNER_SCHEMA_VERSION, "anchor_month": config.anchor_month,
        "required_months": months, "partition_lineage": lineage,
        "source_versions": source_versions,
        "region_vocabulary": config.region_vocabulary, "model_version": config.model_version,
        "seed": config.seed, "minimum_role_sample": config.minimum_role_sample,
        "minimum_node_count": config.minimum_node_count, "minimum_edge_count": config.minimum_edge_count,
        "model_settings": {"primary_model": "gadnr", "model_version": config.model_version, "seed": config.seed, "minimum_role_sample": config.minimum_role_sample},
        "analysis_schema_version": PIPELINE_SCHEMA_VERSION, "fact_schema_version": FACT_SCHEMA_VERSION,
        "run_status": run_status, "feature_fingerprint": pipeline_manifest["feature_fingerprint"],
        "graph_summary": pipeline_manifest["graph_summary"],
    }
    run_fingerprint = _fingerprint(run_input)
    run_directory = config.output_root / f"anchor_month={config.anchor_month}"
    qa_path, service_path, manifest_path = (run_directory / QA_FILENAME, run_directory / SERVICE_FILENAME, run_directory / MANIFEST_FILENAME)
    existing = _existing_status(qa_path=qa_path, service_path=service_path, manifest_path=manifest_path,
                                run_fingerprint=run_fingerprint, qa_sha256=output_sha256[QA_FILENAME], service_sha256=output_sha256[SERVICE_FILENAME])
    if existing == "unchanged":
        return Class1OfflineAnchorRunResult("unchanged", run_status, run_directory, manifest_path, run_fingerprint)
    manifest = {
        **run_input, "run_fingerprint": run_fingerprint, "pipeline_manifest": pipeline_manifest,
        "output_sha256": output_sha256, "output_files": {QA_FILENAME: f"anchor_month={config.anchor_month}/{QA_FILENAME}", SERVICE_FILENAME: f"anchor_month={config.anchor_month}/{SERVICE_FILENAME}"},
        "scope": "local_internal_only", "public_policy_state": "not_applied", "suppression_policy_state": "not_evaluated",
    }
    if existing != "recover":
        _atomic_write(qa_path, qa_bytes)
        _atomic_write(service_path, service_bytes)
    _atomic_write(manifest_path, _canonical_json_bytes(manifest))
    return Class1OfflineAnchorRunResult("recovered" if existing == "recover" else "written", run_status, run_directory, manifest_path, run_fingerprint)


def load_config(path: Path) -> Class1OfflineAnchorConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Class1OfflineAnchorRunError("config must be readable JSON") from exc
    required = {"parquet_root", "output_root", "anchor_month", "region_vocabulary", "model_version", "seed", "minimum_role_sample"}
    if set(data) - (required | {"minimum_node_count", "minimum_edge_count"}) or not required.issubset(data):
        raise Class1OfflineAnchorRunError("config has missing or unsupported fields")
    vocabulary = data["region_vocabulary"]
    if not isinstance(vocabulary, list) or not all(isinstance(value, str) for value in vocabulary):
        raise Class1OfflineAnchorRunError("region_vocabulary must be a string array")
    return Class1OfflineAnchorConfig(Path(data["parquet_root"]), Path(data["output_root"]), data["anchor_month"], tuple(vocabulary), data["model_version"], data["seed"], data["minimum_role_sample"], data.get("minimum_node_count", 2), data.get("minimum_edge_count", 1))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the internal Class 1 GAD-NR anchor analysis.")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_class1_offline_anchor(load_config(args.config))
        print(json.dumps(_json_value(result.__dict__), ensure_ascii=False, sort_keys=True))
        return 0
    except Class1OfflineAnchorRunError as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
