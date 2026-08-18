"""Read-only inventory and artifact verification for local analysis handoffs.

This module deliberately composes existing partition readers and serializers; it
does not reimplement analysis, publish artifacts, or read source workbooks.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Sequence

import pyarrow.parquet as pq

from class_1_anomaly_detection.src.offline_anchor_runner import (
    MANIFEST_FILENAME as CLASS1_MANIFEST_FILENAME,
    ONE_HOP_GRAPH_FILENAME,
    QA_FILENAME,
    SERVICE_FILENAME,
)
from data_pipeline.contracts.supply_monthly import FACT_SCHEMA_VERSION, MONTHLY_FACT_COLUMNS
from data_pipeline.offline.class2_analysis_export import (
    MANIFEST_FILENAME as CLASS2_MANIFEST_FILENAME,
    PAYLOAD_FILENAME as CLASS2_PAYLOAD_FILENAME,
)
from data_pipeline.storage.monthly_fact_parquet import DATASET_NAME, PARQUET_FILENAME

CLASS1_HANDOFF_SCHEMA_VERSION = "1.0.0"
CLASS1_CURRENT_MANIFEST_FILENAME = "class1-current.json"
CLASS1_HANDOFF_MANIFEST_FILENAME = "class1-handoff-manifest.json"


class LocalAnalysisToolError(RuntimeError):
    """Raised for an invalid local-analysis inspection request."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LocalAnalysisToolError(f"unreadable JSON artifact: {path.name}") from exc
    if not isinstance(value, dict) or raw != _canonical(value):
        raise LocalAnalysisToolError(f"artifact is not canonical object JSON: {path.name}")
    return value


def inventory_monthly_fact(*, parquet_root: Path, months: Sequence[str] | None = None, limit: int = 20) -> dict[str, Any]:
    """Stream projected Parquet batches into a temporary bounded-distinct index."""
    if limit < 1:
        raise LocalAnalysisToolError("limit must be positive")
    schema_root = Path(parquet_root) / DATASET_NAME / f"schema_version={FACT_SCHEMA_VERSION}"
    available = sorted(path.name.removeprefix("month=") for path in schema_root.glob("month=*") if path.is_dir()) if schema_root.is_dir() else []
    selected = sorted(months) if months is not None else available
    if any(month not in available for month in selected):
        raise LocalAnalysisToolError("requested month partition is unavailable")
    paths = [schema_root / f"month={month}" / PARQUET_FILENAME for month in selected]
    if any(not path.is_file() for path in paths):
        raise LocalAnalysisToolError("monthly partition is incomplete")
    with tempfile.TemporaryDirectory(prefix="nids-inventory-") as temporary:
        connection = sqlite3.connect(Path(temporary) / "distinct.sqlite")
        connection.execute("create table value_sets (kind text not null, value text not null, parent text, unique(kind,value,parent))")
        invalid_names = 0; row_count = 0
        columns = ["item_group_id", "item_name_id", "src_company_id", "dst_company_id", "supplier_type", "receiver_type", "supplier_region", "receiver_region"]
        for path in paths:
            file = pq.ParquetFile(path); row_count += file.metadata.num_rows
            for batch in file.iter_batches(batch_size=65_536, columns=columns):
                values = batch.to_pydict()
                for index in range(batch.num_rows):
                    group, name = values["item_group_id"][index], values["item_name_id"][index]
                    if group is not None: connection.execute("insert or ignore into value_sets values ('item_group', ?, null)", (str(group),))
                    if name is not None and group is not None: connection.execute("insert or ignore into value_sets values ('item_name', ?, ?)", (str(name), str(group)))
                    elif name is not None: invalid_names += 1
                    for kind, value in (("entity", values["src_company_id"][index]), ("entity", values["dst_company_id"][index]), ("supplier_type", values["supplier_type"][index]), ("receiver_type", values["receiver_type"][index]), ("supplier_region", values["supplier_region"][index]), ("receiver_region", values["receiver_region"][index])):
                        if value is not None: connection.execute("insert or ignore into value_sets values (?, ?, null)", (kind, str(value)))
        connection.commit()
        def values(kind: str, *, scoped: bool = False) -> dict[str, Any]:
            total = connection.execute("select count(*) from value_sets where kind=?", (kind,)).fetchone()[0]
            rows = connection.execute("select value,parent from value_sets where kind=? order by value,parent limit ?", (kind, limit)).fetchall()
            rendered = ([{"parent_item_group": parent, "item_name": value} for value, parent in rows] if scoped else [value for value, _ in rows])
            return {"values": rendered, "omitted_count": total - len(rows)}
        result = {"command": "inventory", "fact_schema_version": FACT_SCHEMA_VERSION, "required_columns": list(MONTHLY_FACT_COLUMNS), "months": {"values": selected[:limit], "omitted_count": len(selected) - min(len(selected), limit)}, "row_count": row_count, "item_groups": values("item_group"), "item_names_parent_scoped": values("item_name", scoped=True), "item_names_excluded_missing_parent_count": invalid_names, "class1_selected_entity_ids": values("entity"), "supplier_types": values("supplier_type"), "receiver_types": values("receiver_type"), "supplier_regions": values("supplier_region"), "receiver_regions": values("receiver_region"), "analysis_available": bool(row_count)}
        connection.close(); return result


def verify_class2_artifact(*, web_public_root: Path) -> dict[str, Any]:
    directory = Path(web_public_root) / "generated"
    payload_path, manifest_path = directory / CLASS2_PAYLOAD_FILENAME, directory / CLASS2_MANIFEST_FILENAME
    payload, manifest = _read_json(payload_path), _read_json(manifest_path)
    if sha256(payload_path.read_bytes()).hexdigest() != manifest.get("payload_sha256"):
        raise LocalAnalysisToolError("Class 2 payload checksum disagrees with manifest")
    if payload.get("analysis_schema_version") != manifest.get("analysis_schema_version"):
        raise LocalAnalysisToolError("Class 2 analysis schema version mismatch")
    if payload.get("local_export", {}).get("publication_scope") != "local_only":
        raise LocalAnalysisToolError("Class 2 artifact is not marked local_only")
    for item in payload.get("selection_catalog", []):
        if item.get("selection_type") == "item_name" and not item.get("parent_item_group_selection_id"):
            raise LocalAnalysisToolError("Class 2 item-name selection lacks parent scope")
    return {"command": "verify-class2", "status": "verified", "local_only": True, "payload_sha256": manifest["payload_sha256"], "export_state": manifest.get("export_state")}


def verify_class1_artifact(*, output_root: Path, anchor_month: str) -> dict[str, Any]:
    directory = Path(output_root) / f"anchor_month={anchor_month}"
    manifest = _read_json(directory / CLASS1_MANIFEST_FILENAME)
    payloads = {name: directory / name for name in (QA_FILENAME, SERVICE_FILENAME, ONE_HOP_GRAPH_FILENAME)}
    service, graph = _read_json(payloads[SERVICE_FILENAME]), _read_json(payloads[ONE_HOP_GRAPH_FILENAME])
    if service.get("run_status") not in {"completed", "insufficient_graph"}:
        raise LocalAnalysisToolError("Class 1 run_status is unsupported")
    if "raw_score" in _canonical(service).decode("utf-8") or "raw_score" in _canonical(graph).decode("utf-8"):
        raise LocalAnalysisToolError("service-safe or graph artifact exposes raw_score")
    if manifest.get("selected_entity_id") != graph.get("selected_entity_id") or manifest.get("anchor_month") != anchor_month:
        raise LocalAnalysisToolError("Class 1 identity disagrees with manifest")
    for name, path in payloads.items():
        if sha256(path.read_bytes()).hexdigest() != manifest.get("output_sha256", {}).get(name):
            raise LocalAnalysisToolError(f"Class 1 checksum mismatch: {name}")
    if "public/generated" in str(directory).replace("\\", "/"):
        raise LocalAnalysisToolError("restricted Class 1 output cannot be under web/public/generated")
    return {"command": "verify-class1", "status": "verified", "run_status": service["run_status"], "anchor_month": anchor_month, "selected_entity_id": graph["selected_entity_id"]}


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name); stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    try: os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True); raise


def verify_class1_web_artifact(*, web_public_root: Path, anchor_month: str | None = None, selected_entity_id: str | None = None) -> dict[str, Any]:
    """Verify current marker, immutable generation manifest, and both safe payloads."""
    root = Path(web_public_root) / "generated"
    current = _read_json(root / CLASS1_CURRENT_MANIFEST_FILENAME)
    generation = current.get("generation")
    if current.get("handoff_schema_version") != CLASS1_HANDOFF_SCHEMA_VERSION or not isinstance(generation, str):
        raise LocalAnalysisToolError("Class 1 current handoff manifest is invalid")
    directory = root / generation
    handoff = _read_json(directory / CLASS1_HANDOFF_MANIFEST_FILENAME)
    if handoff != current or not generation.startswith("generations/"):
        raise LocalAnalysisToolError("Class 1 current marker does not match immutable generation")
    service_path, graph_path = directory / SERVICE_FILENAME, directory / ONE_HOP_GRAPH_FILENAME
    service, graph = _read_json(service_path), _read_json(graph_path)
    if handoff.get("checksums") != {SERVICE_FILENAME: sha256(service_path.read_bytes()).hexdigest(), ONE_HOP_GRAPH_FILENAME: sha256(graph_path.read_bytes()).hexdigest()}:
        raise LocalAnalysisToolError("published Class 1 generation checksum mismatch")
    if service.get("run_status") != handoff.get("run_status") or graph.get("anchor_month") != handoff.get("anchor_month") or graph.get("selected_entity_id") != handoff.get("selected_entity_id"):
        raise LocalAnalysisToolError("published Class 1 web artifact identity or status is invalid")
    if anchor_month is not None and anchor_month != handoff["anchor_month"] or selected_entity_id is not None and selected_entity_id != handoff["selected_entity_id"]:
        raise LocalAnalysisToolError("published Class 1 web artifact does not match requested identity")
    if "raw_score" in _canonical(service).decode("utf-8") or "raw_score" in _canonical(graph).decode("utf-8"):
        raise LocalAnalysisToolError("published Class 1 web artifact exposes raw_score")
    return {"command": "verify-class1-web", "status": "verified", **handoff}


def _overlaps(first: Path, second: Path) -> bool:
    left, right = first.resolve(strict=False), second.resolve(strict=False)
    try: left.relative_to(right); return True
    except ValueError:
        try: right.relative_to(left); return True
        except ValueError: return False


def publish_class1_web_artifact(*, output_root: Path, web_public_root: Path, anchor_month: str) -> dict[str, Any]:
    """Publish a complete immutable generation, then atomically advance current."""
    source = verify_class1_artifact(output_root=output_root, anchor_month=anchor_month)
    destination = Path(web_public_root) / "generated"
    if _overlaps(Path(output_root), destination):
        raise LocalAnalysisToolError("Class 1 source output and web generated paths must be disjoint")
    source_dir = Path(output_root) / f"anchor_month={anchor_month}"
    source_files = {name: source_dir / name for name in (SERVICE_FILENAME, ONE_HOP_GRAPH_FILENAME)}
    checksums = {name: sha256(path.read_bytes()).hexdigest() for name, path in source_files.items()}
    identity = {"handoff_schema_version": CLASS1_HANDOFF_SCHEMA_VERSION, "anchor_month": anchor_month, "selected_entity_id": source["selected_entity_id"], "run_status": source["run_status"], "checksums": checksums}
    generation_id = sha256(_canonical(identity)).hexdigest()
    handoff = {**identity, "generation": f"generations/{generation_id}"}
    generation = destination / handoff["generation"]
    current_path = destination / CLASS1_CURRENT_MANIFEST_FILENAME
    if current_path.is_file():
        try:
            if _read_json(current_path) == handoff:
                verify_class1_web_artifact(web_public_root=web_public_root); return {**source, "command": "publish-class1-web", "status": "unchanged"}
        except LocalAnalysisToolError: pass
    if generation.exists():
        if _read_json(generation / CLASS1_HANDOFF_MANIFEST_FILENAME) != handoff: raise LocalAnalysisToolError("existing Class 1 generation conflicts")
    else:
        destination.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".nids-class1-generation-", dir=destination))
        try:
            for name, path in source_files.items(): shutil.copyfile(path, staging / name)
            for name in source_files:
                if sha256((staging / name).read_bytes()).hexdigest() != checksums[name]: raise LocalAnalysisToolError("staged Class 1 generation checksum mismatch")
            _atomic_write(staging / CLASS1_HANDOFF_MANIFEST_FILENAME, _canonical(handoff))
            generation.parent.mkdir(parents=True, exist_ok=True); os.replace(staging, generation)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True); raise
    _atomic_write(current_path, _canonical(handoff))
    verify_class1_web_artifact(web_public_root=web_public_root)
    return {**source, "command": "publish-class1-web", "status": "written", "generation": handoff["generation"]}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only inventory and verification for local analysis artifacts.")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory"); inventory.add_argument("--parquet-root", required=True, type=Path); inventory.add_argument("--month", action="append"); inventory.add_argument("--limit", type=int, default=20)
    class2 = commands.add_parser("verify-class2"); class2.add_argument("--web-public-root", required=True, type=Path)
    class1 = commands.add_parser("verify-class1"); class1.add_argument("--output-root", required=True, type=Path); class1.add_argument("--anchor-month", required=True)
    web = commands.add_parser("verify-class1-web"); web.add_argument("--web-public-root", required=True, type=Path); web.add_argument("--anchor-month", required=True); web.add_argument("--selected-entity-id", required=True)
    publish = commands.add_parser("publish-class1-web"); publish.add_argument("--output-root", required=True, type=Path); publish.add_argument("--web-public-root", required=True, type=Path); publish.add_argument("--anchor-month", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory": result = inventory_monthly_fact(parquet_root=args.parquet_root, months=args.month, limit=args.limit)
        elif args.command == "verify-class2": result = verify_class2_artifact(web_public_root=args.web_public_root)
        elif args.command == "verify-class1": result = verify_class1_artifact(output_root=args.output_root, anchor_month=args.anchor_month)
        elif args.command == "verify-class1-web": result = verify_class1_web_artifact(web_public_root=args.web_public_root, anchor_month=args.anchor_month, selected_entity_id=args.selected_entity_id)
        else: result = publish_class1_web_artifact(output_root=args.output_root, web_public_root=args.web_public_root, anchor_month=args.anchor_month)
        print(_canonical(result).decode("utf-8")); return 0
    except LocalAnalysisToolError as exc:
        print(_canonical({"error": type(exc).__name__, "message": str(exc)}).decode("utf-8")); return 2


if __name__ == "__main__":
    raise SystemExit(main())
