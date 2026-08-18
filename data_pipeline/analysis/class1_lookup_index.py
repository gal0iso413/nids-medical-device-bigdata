"""Materialize a Class 1 entity lookup index from one completed GAD-NR run.

This batch reads verified monthly facts and an existing offline-anchor service
payload.  It does not train GAD-NR, and it never writes raw scores.  The index
lets a local lookup API return any graph entity's review row and 1-hop
neighborhood without rebuilding the training graph on request.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets
import shutil
from typing import Any, Final, Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from class_1_anomaly_detection.src.model_pipeline import (
    _json_value,
    build_gadnr_features,
    build_model_graph,
)
from class_1_anomaly_detection.src.offline_anchor_runner import (
    MANIFEST_FILENAME as RUN_MANIFEST_FILENAME,
    SERVICE_FILENAME,
)
from data_pipeline.contracts.supply_monthly import FACT_SCHEMA_VERSION
from data_pipeline.ingest.company_display_name import (
    CompanyDisplayNameError,
    read_company_display_name_directory,
)
from data_pipeline.storage.monthly_fact_parquet import (
    DATASET_NAME as FACT_DATASET_NAME,
    LOGICAL_SCHEMA_FINGERPRINT,
    PartitionVerification,
    read_monthly_fact_partitions,
    verify_monthly_fact_partition,
)


LOOKUP_INDEX_SCHEMA_VERSION: Final = "1.2.0"
LOOKUP_INDEX_DATASET_NAME: Final = "class1_lookup_index"
MANIFEST_FILENAME: Final = "_manifest.json"
CATALOG_FILENAME: Final = "_catalog.json"
_ANCHOR_DIR_PATTERN: Final = re.compile(r"^anchor_month=(\d{6})$")
_INDEX_FILENAMES: Final[dict[str, str]] = {
    "entities": "entities.parquet",
    "nodes": "nodes.parquet",
    "edges": "edges.parquet",
    "names": "names.parquet",
}


class Class1LookupIndexError(RuntimeError):
    """Raised when a Class 1 lookup index cannot be built safely."""


class Class1LookupIndexConflictError(Class1LookupIndexError):
    """Raised rather than replacing an existing index with different content."""


@dataclass(frozen=True)
class Class1LookupIndexResult:
    status: Literal["written", "unchanged"]
    output_path: Path
    manifest_path: Path
    created_fingerprint: str
    row_counts: dict[str, int]


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return sha256(_canonical_json_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _validate_roots(fact_root: Path, run_root: Path, output_root: Path) -> None:
    if not isinstance(fact_root, Path) or not isinstance(run_root, Path) or not isinstance(output_root, Path):
        raise TypeError("fact_root, run_root, and output_root must be pathlib.Path values")
    if _is_within(output_root, fact_root) or _is_within(fact_root, output_root):
        raise Class1LookupIndexError("output_root must not overlap fact_root")
    if _is_within(output_root, run_root) or _is_within(run_root, output_root):
        raise Class1LookupIndexError("output_root must not overlap the offline-anchor run root")


def _schema_dir(output_root: Path) -> Path:
    return output_root / LOOKUP_INDEX_DATASET_NAME / f"schema_version={LOOKUP_INDEX_SCHEMA_VERSION}"


def _partition_dir(output_root: Path, anchor_month: str) -> Path:
    return _schema_dir(output_root) / f"anchor_month={anchor_month}"


def _run_directory(run_root: Path, anchor_month: str) -> Path:
    return Path(run_root) / f"anchor_month={anchor_month}"


def _load_completed_run(run_root: Path, anchor_month: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    directory = _run_directory(run_root, anchor_month)
    manifest_path = directory / RUN_MANIFEST_FILENAME
    service_path = directory / SERVICE_FILENAME
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        service_bytes = service_path.read_bytes()
        service = json.loads(service_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Class1LookupIndexError("completed offline-anchor run payloads are unreadable") from exc
    if not isinstance(manifest, dict) or manifest_bytes != _canonical_json_bytes(manifest):
        raise Class1LookupIndexError("offline-anchor run manifest is not canonical")
    if not isinstance(service, dict) or service_bytes != _canonical_json_bytes(service):
        raise Class1LookupIndexError("offline-anchor service payload is not canonical")
    if manifest.get("run_status") != "completed" or service.get("run_status") != "completed":
        raise Class1LookupIndexError("lookup index requires a completed GAD-NR run")
    expected = manifest.get("output_sha256", {}).get(SERVICE_FILENAME)
    if not isinstance(expected, str) or sha256(service_bytes).hexdigest() != expected:
        raise Class1LookupIndexError("offline-anchor service checksum does not match the run manifest")
    if "raw_score" in json.dumps(service, ensure_ascii=False):
        raise Class1LookupIndexError("raw_score cannot enter the lookup index")
    results = service.get("service_results")
    if not isinstance(results, list) or not results:
        raise Class1LookupIndexError("completed service payload must contain service_results")
    return manifest, results


def _source_lineage(verifications: tuple[PartitionVerification, ...]) -> list[dict[str, Any]]:
    return [
        {
            "month": item.month,
            "row_count": item.row_count,
            "relative_parquet_path": item.relative_parquet_path,
            "parquet_sha256": item.parquet_sha256,
            "parquet_file_size": item.parquet_file_size,
        }
        for item in verifications
    ]


def _load_display_names(name_root: Path) -> tuple[dict[str, dict[str, Any]], str | None]:
    try:
        loaded = read_company_display_name_directory(name_root)
    except CompanyDisplayNameError as exc:
        raise Class1LookupIndexError("display-name directory is unreadable") from exc
    if loaded is None:
        return {}, None
    manifest, frame = loaded
    mapping: dict[str, dict[str, Any]] = {}
    for row in frame.itertuples(index=False):
        mapping[str(row.entity_id)] = {
            "display_name": None if pd.isna(row.display_name) else str(row.display_name),
            "name_conflict": bool(row.name_conflict),
        }
    fingerprint = manifest.get("created_fingerprint")
    if not isinstance(fingerprint, str):
        raise Class1LookupIndexError("display-name directory fingerprint is invalid")
    return mapping, fingerprint


def _write_parquet(path: Path, frame: pd.DataFrame, schema: pa.Schema) -> None:
    table = pa.Table.from_pandas(frame, schema=schema, preserve_index=False)
    pq.write_table(table, path, compression="zstd")


def _build_frames(
    *,
    fact: pd.DataFrame,
    service_results: list[dict[str, Any]],
    run_manifest: dict[str, Any],
    display_names: dict[str, dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    graph = build_model_graph(fact, anchor_month=run_manifest["anchor_month"])
    vocabulary = tuple(run_manifest["region_vocabulary"])
    _features, feature_manifest = build_gadnr_features(fact, graph, region_vocabulary=vocabulary)
    expected_summary = run_manifest["graph_summary"]
    actual_summary = {
        "node_count": len(graph.nodes),
        "edge_count": int(len(graph.edges)),
        "self_loop_count": int(graph.self_loop_count),
    }
    if actual_summary != expected_summary:
        raise Class1LookupIndexError("offline-anchor graph summary does not match rebuilt model graph")
    entity_ids = [str(row.get("entity_id", "")) for row in service_results]
    if sorted(entity_ids) != sorted(graph.nodes) or len(set(entity_ids)) != len(entity_ids):
        raise Class1LookupIndexError("service_results entities must exactly match model-graph nodes")
    metadata = feature_manifest["entity_metadata"]
    entities = pd.DataFrame({
        "entity_id": pd.Series(entity_ids, dtype="string"),
        "service_row_json": pd.Series(
            [_canonical_json_bytes(row).decode("utf-8") for row in service_results],
            dtype="string",
        ),
    }).sort_values("entity_id", kind="stable").reset_index(drop=True)
    nodes = pd.DataFrame([
        {
            "entity_id": entity_id,
            "role_group": metadata[entity_id]["role_group"],
            "region": metadata[entity_id]["region"],
            "region_missing_or_conflict": bool(metadata[entity_id]["region_missing_or_conflict"]),
        }
        for entity_id in graph.nodes
    ])
    nodes["entity_id"] = nodes["entity_id"].astype("string")
    nodes["role_group"] = nodes["role_group"].astype("string")
    nodes["region"] = nodes["region"].astype("string")
    edge_records = _json_value(graph.edges.to_dict("records"))
    edges = pd.DataFrame(edge_records)
    if edges.empty:
        edges = pd.DataFrame(columns=[
            "src_company_id", "dst_company_id", "tx_count", "unique_product_count",
            "active_month_count", "amount_sum_clean", "amount_valid_row_count",
            "amount_valid_rate", "raw_supply_qty_sum", "raw_supply_qty_valid_row_count",
            "raw_supply_qty_valid_rate", "piece_qty_sum", "piece_qty_valid_row_count",
            "piece_qty_valid_rate",
        ])
    for column in ("src_company_id", "dst_company_id"):
        edges[column] = edges[column].astype("string")
    for column in (
        "amount_sum_clean", "amount_valid_rate", "raw_supply_qty_sum",
        "raw_supply_qty_valid_rate", "piece_qty_sum", "piece_qty_valid_rate",
    ):
        edges[column] = edges[column].map(lambda value: None if value is None else str(value)).astype("string")
    extras = {
        "window_months": list(graph.window_months),
        "feature_fingerprint": feature_manifest["feature_fingerprint"],
        "graph_fingerprint": run_manifest["pipeline_manifest"]["graph_fingerprint"],
        "run_fingerprint": run_manifest["run_fingerprint"],
        "self_loop_count": int(graph.self_loop_count),
    }
    names = pd.DataFrame(
        [
            {
                "entity_id": entity_id,
                "display_name": display_names.get(entity_id, {}).get("display_name"),
                "name_conflict": bool(display_names.get(entity_id, {}).get("name_conflict", False)),
            }
            for entity_id in graph.nodes
        ]
    )
    names["entity_id"] = names["entity_id"].astype("string")
    names["display_name"] = names["display_name"].astype("string")
    names["name_conflict"] = names["name_conflict"].astype("bool")
    names = names.sort_values("entity_id", kind="stable").reset_index(drop=True)
    return entities, nodes, edges, names, extras


def _candidate_manifest(
    *,
    run_manifest: dict[str, Any],
    verifications: tuple[PartitionVerification, ...],
    row_counts: dict[str, int],
    hashes: dict[str, str],
    extras: dict[str, Any],
    name_directory_fingerprint: str | None,
) -> dict[str, Any]:
    fingerprint_input = {
        "lookup_index_dataset_name": LOOKUP_INDEX_DATASET_NAME,
        "lookup_index_schema_version": LOOKUP_INDEX_SCHEMA_VERSION,
        "fact_dataset_name": FACT_DATASET_NAME,
        "fact_schema_version": FACT_SCHEMA_VERSION,
        "fact_schema_fingerprint": LOGICAL_SCHEMA_FINGERPRINT,
        "anchor_month": run_manifest["anchor_month"],
        "window_months": extras["window_months"],
        "run_fingerprint": extras["run_fingerprint"],
        "feature_fingerprint": extras["feature_fingerprint"],
        "graph_fingerprint": extras["graph_fingerprint"],
        "name_directory_fingerprint": name_directory_fingerprint,
        "source_partitions": _source_lineage(verifications),
        "output_sha256": hashes,
        "graph_summary": run_manifest["graph_summary"],
        "model_settings": {
            "primary_model": "gadnr",
            "model_version": run_manifest["model_version"],
            "seed": run_manifest["seed"],
        },
    }
    return {
        **fingerprint_input,
        "created_fingerprint": _fingerprint(fingerprint_input),
        "entity_count": row_counts["entities"],
        "outputs": [
            {
                "name": name,
                "filename": _INDEX_FILENAMES[name],
                "row_count": row_counts[name],
                "sha256": hashes[name],
            }
            for name in sorted(_INDEX_FILENAMES)
        ],
        "scope": "local_internal_only",
        "public_policy_state": "not_applied",
        "trains_on_request": False,
    }


def _write_outputs(
    staging: Path,
    entities: pd.DataFrame,
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    names: pd.DataFrame,
) -> tuple[dict[str, int], dict[str, str]]:
    schemas = {
        "entities": pa.schema([
            pa.field("entity_id", pa.string()),
            pa.field("service_row_json", pa.string()),
        ]),
        "nodes": pa.schema([
            pa.field("entity_id", pa.string()),
            pa.field("role_group", pa.string()),
            pa.field("region", pa.string()),
            pa.field("region_missing_or_conflict", pa.bool_()),
        ]),
        "edges": pa.schema([
            pa.field("src_company_id", pa.string()),
            pa.field("dst_company_id", pa.string()),
            pa.field("tx_count", pa.int64()),
            pa.field("unique_product_count", pa.int64()),
            pa.field("active_month_count", pa.int64()),
            pa.field("amount_sum_clean", pa.string()),
            pa.field("amount_valid_row_count", pa.int64()),
            pa.field("amount_valid_rate", pa.string()),
            pa.field("raw_supply_qty_sum", pa.string()),
            pa.field("raw_supply_qty_valid_row_count", pa.int64()),
            pa.field("raw_supply_qty_valid_rate", pa.string()),
            pa.field("piece_qty_sum", pa.string()),
            pa.field("piece_qty_valid_row_count", pa.int64()),
            pa.field("piece_qty_valid_rate", pa.string()),
        ]),
        "names": pa.schema([
            pa.field("entity_id", pa.string()),
            pa.field("display_name", pa.string()),
            pa.field("name_conflict", pa.bool_()),
        ]),
    }
    frames = {"entities": entities, "nodes": nodes, "edges": edges, "names": names}
    row_counts: dict[str, int] = {}
    hashes: dict[str, str] = {}
    for name, frame in frames.items():
        path = staging / _INDEX_FILENAMES[name]
        _write_parquet(path, frame, schemas[name])
        row_counts[name] = int(len(frame))
        hashes[name] = _sha256_file(path)
    return row_counts, hashes


def _new_staging_dir(final_dir: Path) -> Path:
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        candidate = final_dir.parent / f".{final_dir.name}.tmp-{secrets.token_hex(8)}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise Class1LookupIndexError("could not allocate lookup index staging directory")


def _existing_matches(final_dir: Path, candidate: dict[str, Any]) -> bool:
    path = final_dir / MANIFEST_FILENAME
    if not path.is_file():
        return False
    try:
        raw = path.read_bytes()
        existing = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Class1LookupIndexConflictError("existing lookup index manifest is unreadable") from exc
    if not isinstance(existing, dict) or raw != _canonical_json_bytes(existing):
        raise Class1LookupIndexConflictError("existing lookup index manifest is not canonical")
    if existing.get("created_fingerprint") != candidate["created_fingerprint"] or existing != candidate:
        return False
    for output in candidate["outputs"]:
        file_path = final_dir / output["filename"]
        if not file_path.is_file() or _sha256_file(file_path) != output["sha256"]:
            return False
    return True


def _partition_catalog_entry(partition_dir: Path) -> dict[str, Any]:
    path = partition_dir / MANIFEST_FILENAME
    try:
        raw = path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Class1LookupIndexError("lookup index partition manifest is unreadable") from exc
    if not isinstance(manifest, dict) or raw != _canonical_json_bytes(manifest):
        raise Class1LookupIndexError("lookup index partition manifest is not canonical")
    summary = manifest.get("graph_summary")
    if not isinstance(summary, dict) or "edge_count" not in summary:
        raise Class1LookupIndexError("lookup index partition graph_summary is invalid")
    window = manifest.get("window_months")
    if not isinstance(window, list) or not all(isinstance(item, str) for item in window):
        raise Class1LookupIndexError("lookup index partition window_months is invalid")
    return {
        "anchor_month": str(manifest["anchor_month"]),
        "created_fingerprint": str(manifest["created_fingerprint"]),
        "entity_count": int(manifest["entity_count"]),
        "edge_count": int(summary["edge_count"]),
        "window_months": list(window),
    }


def _catalog_payload(partitions: list[dict[str, Any]]) -> dict[str, Any]:
    months = [str(item["anchor_month"]) for item in partitions]
    fingerprint_input = {
        "lookup_index_dataset_name": LOOKUP_INDEX_DATASET_NAME,
        "lookup_index_schema_version": LOOKUP_INDEX_SCHEMA_VERSION,
        "available_anchor_months": months,
        "default_anchor_month": months[-1],
        "partitions": partitions,
        "scope": "local_internal_only",
        "trains_on_request": False,
    }
    return {
        **fingerprint_input,
        "created_fingerprint": _fingerprint(fingerprint_input),
    }


def _refresh_catalog(schema_dir: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    if schema_dir.is_dir():
        for child in sorted(schema_dir.iterdir(), key=lambda item: item.name):
            if not child.is_dir() or child.name.startswith("."):
                continue
            match = _ANCHOR_DIR_PATTERN.fullmatch(child.name)
            if match is None:
                continue
            entry = _partition_catalog_entry(child)
            if entry["anchor_month"] != match.group(1):
                raise Class1LookupIndexError("lookup index partition directory does not match its manifest")
            entries.append(entry)
    if not entries:
        raise Class1LookupIndexError("lookup index catalog requires at least one anchor partition")
    catalog = _catalog_payload(entries)
    encoded = _canonical_json_bytes(catalog)
    dest = schema_dir / CATALOG_FILENAME
    if dest.is_file() and dest.read_bytes() == encoded:
        return catalog
    tmp = schema_dir / f".{CATALOG_FILENAME}.tmp-{secrets.token_hex(8)}"
    tmp.write_bytes(encoded)
    tmp.replace(dest)
    return catalog


def build_class1_lookup_index(
    *,
    fact_root: Path,
    run_root: Path,
    output_root: Path,
    anchor_month: str,
    name_root: Path | None = None,
) -> Class1LookupIndexResult:
    """Materialize an immutable lookup index for one completed anchor run."""
    _validate_roots(fact_root, run_root, output_root)
    resolved_name_root = fact_root if name_root is None else Path(name_root)
    run_manifest, service_results = _load_completed_run(run_root, anchor_month)
    months = tuple(run_manifest["required_months"])
    try:
        verifications = tuple(verify_monthly_fact_partition(fact_root, month) for month in months)
        fact = read_monthly_fact_partitions(fact_root, months=months)
    except Exception as exc:
        raise Class1LookupIndexError("all six required monthly partitions must exist and pass checksum verification") from exc
    display_names, name_directory_fingerprint = _load_display_names(resolved_name_root)
    entities, nodes, edges, names, extras = _build_frames(
        fact=fact, service_results=service_results, run_manifest=run_manifest,
        display_names=display_names,
    )
    final_dir = _partition_dir(output_root, str(run_manifest["anchor_month"]))
    staging = _new_staging_dir(final_dir)
    try:
        row_counts, hashes = _write_outputs(staging, entities, nodes, edges, names)
        candidate = _candidate_manifest(
            run_manifest=run_manifest, verifications=verifications,
            row_counts=row_counts, hashes=hashes, extras=extras,
            name_directory_fingerprint=name_directory_fingerprint,
        )
        (staging / MANIFEST_FILENAME).write_bytes(_canonical_json_bytes(candidate))
        if final_dir.exists():
            if _existing_matches(final_dir, candidate):
                shutil.rmtree(staging)
                _refresh_catalog(_schema_dir(output_root))
                return Class1LookupIndexResult("unchanged", final_dir, final_dir / MANIFEST_FILENAME, candidate["created_fingerprint"], row_counts)
            raise Class1LookupIndexConflictError("existing lookup index has different content; refusing overwrite")
        staging.replace(final_dir)
        _refresh_catalog(_schema_dir(output_root))
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return Class1LookupIndexResult("written", final_dir, final_dir / MANIFEST_FILENAME, candidate["created_fingerprint"], row_counts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a Class 1 lookup index from a completed GAD-NR run.")
    parser.add_argument("--fact-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--anchor-month", required=True)
    parser.add_argument("--name-root", type=Path)
    args = parser.parse_args(argv)
    try:
        result = build_class1_lookup_index(
            fact_root=args.fact_root, run_root=args.run_root,
            output_root=args.output_root, anchor_month=args.anchor_month,
            name_root=args.name_root,
        )
    except Class1LookupIndexError as exc:
        print(_canonical_json_bytes({"error": type(exc).__name__, "message": str(exc)}).decode("utf-8"))
        return 2
    print(_canonical_json_bytes({
        "status": result.status,
        "created_fingerprint": result.created_fingerprint,
        "entity_count": result.row_counts["entities"],
        "edge_count": result.row_counts["edges"],
    }).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
