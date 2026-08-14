"""Read-only inventory and artifact verification for local analysis handoffs.

This module deliberately composes existing partition readers and serializers; it
does not reimplement analysis, publish artifacts, or read source workbooks.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from class_1_anomaly_detection.src.offline_anchor_runner import (
    MANIFEST_FILENAME as CLASS1_MANIFEST_FILENAME,
    ONE_HOP_GRAPH_FILENAME,
    QA_FILENAME,
    SERVICE_FILENAME,
)
from data_pipeline.contracts.supply_monthly import FACT_SCHEMA_VERSION, MONTHLY_FACT_COLUMNS
from data_pipeline.offline.class3_analysis_export import (
    MANIFEST_FILENAME as CLASS3_MANIFEST_FILENAME,
    PAYLOAD_FILENAME as CLASS3_PAYLOAD_FILENAME,
)
from data_pipeline.storage.monthly_fact_parquet import read_monthly_fact_partitions


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


def _bounded(values: Iterable[Any], limit: int) -> dict[str, Any]:
    if limit < 1:
        raise LocalAnalysisToolError("limit must be positive")
    unique = sorted({str(value) for value in values if value is not None and str(value)})
    return {"values": unique[:limit], "omitted_count": max(0, len(unique) - limit)}


def inventory_monthly_fact(*, parquet_root: Path, months: Sequence[str] | None = None, limit: int = 20) -> dict[str, Any]:
    """Return deterministic, bounded analysis choices from projected fact columns."""
    columns = (
        "month", "item_group_id", "item_name_id", "src_company_id", "dst_company_id",
        "supplier_type", "receiver_type", "supplier_region", "receiver_region",
    )
    fact = read_monthly_fact_partitions(Path(parquet_root), months=months, columns=columns)
    groups = _bounded(fact["item_group_id"].dropna(), limit)
    names: list[dict[str, Any]] = []
    scoped = fact.loc[:, ["item_group_id", "item_name_id"]].dropna(subset=["item_name_id"])
    for (parent, name), _ in scoped.groupby(["item_group_id", "item_name_id"], dropna=False, sort=True):
        names.append({"parent_item_group": None if parent is None else str(parent), "item_name": str(name)})
    names = names[:limit]
    entity_ids = _bounded([*fact["src_company_id"].dropna(), *fact["dst_company_id"].dropna()], limit)
    return {
        "command": "inventory", "fact_schema_version": FACT_SCHEMA_VERSION,
        "required_columns": list(MONTHLY_FACT_COLUMNS),
        "months": _bounded(fact["month"].dropna(), limit), "row_count": len(fact),
        "item_groups": groups,
        "item_names_parent_scoped": {"values": names, "omitted_count": max(0, len(scoped.drop_duplicates()) - len(names))},
        "class1_selected_entity_ids": entity_ids,
        "supplier_types": _bounded(fact["supplier_type"].dropna(), limit),
        "receiver_types": _bounded(fact["receiver_type"].dropna(), limit),
        "supplier_regions": _bounded(fact["supplier_region"].dropna(), limit),
        "receiver_regions": _bounded(fact["receiver_region"].dropna(), limit),
        "analysis_available": not fact.empty,
    }


def verify_class3_artifact(*, web_public_root: Path) -> dict[str, Any]:
    directory = Path(web_public_root) / "generated"
    payload_path, manifest_path = directory / CLASS3_PAYLOAD_FILENAME, directory / CLASS3_MANIFEST_FILENAME
    payload, manifest = _read_json(payload_path), _read_json(manifest_path)
    if sha256(payload_path.read_bytes()).hexdigest() != manifest.get("payload_sha256"):
        raise LocalAnalysisToolError("Class 3 payload checksum disagrees with manifest")
    if payload.get("analysis_schema_version") != manifest.get("analysis_schema_version"):
        raise LocalAnalysisToolError("Class 3 analysis schema version mismatch")
    if payload.get("local_export", {}).get("publication_scope") != "local_only":
        raise LocalAnalysisToolError("Class 3 artifact is not marked local_only")
    for item in payload.get("selection_catalog", []):
        if item.get("selection_type") == "item_name" and not item.get("parent_item_group_selection_id"):
            raise LocalAnalysisToolError("Class 3 item-name selection lacks parent scope")
    return {"command": "verify-class3", "status": "verified", "local_only": True, "payload_sha256": manifest["payload_sha256"], "export_state": manifest.get("export_state")}


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only inventory and verification for local analysis artifacts.")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory"); inventory.add_argument("--parquet-root", required=True, type=Path); inventory.add_argument("--month", action="append"); inventory.add_argument("--limit", type=int, default=20)
    class3 = commands.add_parser("verify-class3"); class3.add_argument("--web-public-root", required=True, type=Path)
    class1 = commands.add_parser("verify-class1"); class1.add_argument("--output-root", required=True, type=Path); class1.add_argument("--anchor-month", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory": result = inventory_monthly_fact(parquet_root=args.parquet_root, months=args.month, limit=args.limit)
        elif args.command == "verify-class3": result = verify_class3_artifact(web_public_root=args.web_public_root)
        else: result = verify_class1_artifact(output_root=args.output_root, anchor_month=args.anchor_month)
        print(_canonical(result).decode("utf-8")); return 0
    except LocalAnalysisToolError as exc:
        print(_canonical({"error": type(exc).__name__, "message": str(exc)}).decode("utf-8")); return 2


if __name__ == "__main__":
    raise SystemExit(main())
