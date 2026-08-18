"""Manifest-verified Class 1 lookup index reader.  Requests never train GAD-NR."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Final

import duckdb
import pyarrow.parquet as pq

from data_pipeline.analysis.class1_lookup_index import (
    LOOKUP_INDEX_DATASET_NAME,
    LOOKUP_INDEX_SCHEMA_VERSION,
    MANIFEST_FILENAME,
)


_ENTITY_PATTERN: Final = re.compile(r"^[A-Za-z0-9:._-]{1,128}$")
_OUTPUTS: Final[frozenset[str]] = frozenset({"entities", "nodes", "edges", "names"})
REVIEW_QUEUE_ROLE_GROUP: Final = "distributor"
REVIEW_QUEUE_LIMIT: Final = 10


class IndexVerificationError(RuntimeError):
    """Raised before startup when a lookup index directory is not trustworthy."""


class LookupContractError(ValueError):
    """Raised when a request falls outside the fixed local lookup contract."""


@dataclass(frozen=True)
class VerifiedIndex:
    root: Path
    fingerprint: str
    anchor_month: str
    window_months: tuple[str, ...]
    entity_count: int
    edge_count: int
    self_loop_count: int
    files: dict[str, Path]


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _index_directory(index_root: Path) -> Path:
    direct = index_root / MANIFEST_FILENAME
    if direct.is_file():
        return index_root
    return index_root / LOOKUP_INDEX_DATASET_NAME / f"schema_version={LOOKUP_INDEX_SCHEMA_VERSION}"


def verify_index(index_root: Path) -> VerifiedIndex:
    """Validate the canonical manifest and every allowlisted materialized file."""
    root = _index_directory(Path(index_root))
    manifest_path = root / MANIFEST_FILENAME
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndexVerificationError("lookup index manifest is unreadable") from exc
    if not isinstance(manifest, dict) or raw != _canonical_json_bytes(manifest):
        raise IndexVerificationError("lookup index manifest is not canonical")
    required = {
        "lookup_index_dataset_name", "lookup_index_schema_version", "fact_dataset_name",
        "fact_schema_version", "fact_schema_fingerprint", "anchor_month", "window_months",
        "run_fingerprint", "feature_fingerprint", "graph_fingerprint", "name_directory_fingerprint",
        "source_partitions",
        "output_sha256", "graph_summary", "model_settings", "created_fingerprint",
        "entity_count", "outputs", "scope", "public_policy_state", "trains_on_request",
    }
    if set(manifest) != required:
        raise IndexVerificationError("lookup index manifest fields are invalid")
    if manifest["lookup_index_dataset_name"] != LOOKUP_INDEX_DATASET_NAME:
        raise IndexVerificationError("lookup index dataset is unsupported")
    if manifest["lookup_index_schema_version"] != LOOKUP_INDEX_SCHEMA_VERSION:
        raise IndexVerificationError("lookup index schema/version is unsupported")
    if manifest["scope"] != "local_internal_only" or manifest["trains_on_request"] is not False:
        raise IndexVerificationError("lookup index scope is not local lookup-only")
    fingerprint_input = {key: manifest[key] for key in (
        "lookup_index_dataset_name", "lookup_index_schema_version", "fact_dataset_name",
        "fact_schema_version", "fact_schema_fingerprint", "anchor_month", "window_months",
        "run_fingerprint", "feature_fingerprint", "graph_fingerprint", "name_directory_fingerprint",
        "source_partitions",
        "output_sha256", "graph_summary", "model_settings",
    )}
    if sha256(_canonical_json_bytes(fingerprint_input)).hexdigest() != manifest["created_fingerprint"]:
        raise IndexVerificationError("lookup index manifest fingerprint is invalid")
    outputs = manifest["outputs"]
    if not isinstance(outputs, list) or {item.get("name") for item in outputs if isinstance(item, dict)} != _OUTPUTS:
        raise IndexVerificationError("lookup index output set is invalid")
    files: dict[str, Path] = {}
    connection = duckdb.connect(database=":memory:")
    try:
        for output in outputs:
            if not isinstance(output, dict) or set(output) != {"name", "filename", "row_count", "sha256"}:
                raise IndexVerificationError("lookup index output metadata is invalid")
            name, filename = output["name"], output["filename"]
            if name not in _OUTPUTS or filename != f"{name}.parquet" or Path(filename).name != filename:
                raise IndexVerificationError("lookup index output path is invalid")
            path = root / filename
            if not _is_inside(path, root) or not path.is_file():
                raise IndexVerificationError("lookup index output is outside root or missing")
            if _sha256_file(path) != output["sha256"] or manifest["output_sha256"].get(name) != output["sha256"]:
                raise IndexVerificationError("lookup index output checksum is invalid")
            escaped = path.as_posix().replace("'", "''")
            row_count = int(connection.execute(
                f"SELECT count(*) FROM read_parquet('{escaped}', hive_partitioning = false)"
            ).fetchone()[0])
            if row_count != output["row_count"] or row_count < 0:
                raise IndexVerificationError("lookup index output row count is invalid")
            files[name] = path
    finally:
        connection.close()
    window = manifest["window_months"]
    if not isinstance(window, list) or not all(isinstance(item, str) for item in window):
        raise IndexVerificationError("lookup index window_months is invalid")
    summary = manifest["graph_summary"]
    if not isinstance(summary, dict) or "self_loop_count" not in summary:
        raise IndexVerificationError("lookup index graph_summary is invalid")
    if manifest["entity_count"] != next(item["row_count"] for item in outputs if item["name"] == "entities"):
        raise IndexVerificationError("lookup index entity_count is invalid")
    return VerifiedIndex(
        root=root,
        fingerprint=str(manifest["created_fingerprint"]),
        anchor_month=str(manifest["anchor_month"]),
        window_months=tuple(window),
        entity_count=int(manifest["entity_count"]),
        edge_count=int(summary["edge_count"]),
        self_loop_count=int(summary["self_loop_count"]),
        files=files,
    )


def _require_entity_id(entity_id: str) -> str:
    if not isinstance(entity_id, str) or not _ENTITY_PATTERN.fullmatch(entity_id):
        raise LookupContractError("entity_id must be a 1-128 character lookup key")
    return entity_id


class IndexReader:
    """In-memory lookup over a verified Class 1 index.  No model execution."""

    def __init__(self, index: VerifiedIndex) -> None:
        self.index = index
        entities = pq.read_table(index.files["entities"]).to_pydict()
        self._service_rows = {
            str(entity_id): json.loads(payload)
            for entity_id, payload in zip(entities["entity_id"], entities["service_row_json"], strict=True)
        }
        nodes = pq.read_table(index.files["nodes"]).to_pydict()
        self._nodes = {
            str(entity_id): {
                "entity_id": str(entity_id),
                "role_group": str(role),
                "region": None if region is None else str(region),
                "region_missing_or_conflict": bool(missing),
            }
            for entity_id, role, region, missing in zip(
                nodes["entity_id"], nodes["role_group"], nodes["region"],
                nodes["region_missing_or_conflict"], strict=True,
            )
        }
        edges = pq.read_table(index.files["edges"]).to_pylist()
        self._edges = [
            {
                "src_company_id": str(row["src_company_id"]),
                "dst_company_id": str(row["dst_company_id"]),
                "tx_count": int(row["tx_count"]),
                "unique_product_count": int(row["unique_product_count"]),
                "active_month_count": int(row["active_month_count"]),
                "amount_sum_clean": None if row["amount_sum_clean"] is None else str(row["amount_sum_clean"]),
                "amount_valid_row_count": int(row["amount_valid_row_count"]),
                "amount_valid_rate": None if row["amount_valid_rate"] is None else str(row["amount_valid_rate"]),
                "raw_supply_qty_sum": None if row["raw_supply_qty_sum"] is None else str(row["raw_supply_qty_sum"]),
                "raw_supply_qty_valid_row_count": int(row["raw_supply_qty_valid_row_count"]),
                "raw_supply_qty_valid_rate": None if row["raw_supply_qty_valid_rate"] is None else str(row["raw_supply_qty_valid_rate"]),
                "piece_qty_sum": None if row["piece_qty_sum"] is None else str(row["piece_qty_sum"]),
                "piece_qty_valid_row_count": int(row["piece_qty_valid_row_count"]),
                "piece_qty_valid_rate": None if row["piece_qty_valid_rate"] is None else str(row["piece_qty_valid_rate"]),
            }
            for row in edges
        ]
        names = pq.read_table(index.files["names"]).to_pydict()
        self._names = {
            str(entity_id): {
                "display_name": None if display_name is None else str(display_name),
                "name_conflict": bool(conflict),
            }
            for entity_id, display_name, conflict in zip(
                names["entity_id"], names["display_name"], names["name_conflict"], strict=True
            )
        }
        if any("raw_score" in json.dumps(row, ensure_ascii=False) for row in self._service_rows.values()):
            raise IndexVerificationError("raw_score cannot leave the lookup index")

    @classmethod
    def open(cls, index_root: Path) -> "IndexReader":
        return cls(verify_index(index_root))

    def close(self) -> None:
        return None

    def review(self, entity_id: str) -> dict[str, Any]:
        selected = _require_entity_id(entity_id)
        row = self._service_rows.get(selected)
        if row is None:
            raise LookupContractError("entity_id is not in the lookup index")
        return {
            "analysis_schema_version": "1.0.0",
            "run_status": "completed",
            "service_results": [row],
        }

    def relationships(self, entity_id: str) -> dict[str, Any]:
        selected = _require_entity_id(entity_id)
        if selected not in self._service_rows:
            raise LookupContractError("entity_id is not in the lookup index")
        scoped = [
            row for row in self._edges
            if row["src_company_id"] == selected or row["dst_company_id"] == selected
        ]
        scoped.sort(key=lambda row: (row["src_company_id"], row["dst_company_id"]))
        node_ids = sorted({row["src_company_id"] for row in scoped} | {row["dst_company_id"] for row in scoped})
        if not node_ids:
            node_ids = [selected]
        nodes = []
        for node_id in node_ids:
            metadata = self._nodes[node_id]
            nodes.append({
                "entity_id": node_id,
                "selected": node_id == selected,
                "role_group": metadata["role_group"],
                "region": metadata["region"],
                "region_missing_or_conflict": metadata["region_missing_or_conflict"],
                "display_name": self._names.get(node_id, {}).get("display_name"),
                "name_conflict": bool(self._names.get(node_id, {}).get("name_conflict", False)),
            })
        return {
            "graph_scope": "one_hop",
            "selected_entity_id": selected,
            "anchor_month": self.index.anchor_month,
            "window_months": list(self.index.window_months),
            "nodes": nodes,
            "edges": scoped,
            "graph_summary": {
                "selected_node_count": 1,
                "one_hop_counterparty_count": max(0, len(node_ids) - 1),
                "edge_count": len(scoped),
                "self_loop_excluded_count": self.index.self_loop_count,
                "truncated": False,
                "truncation_reason": None,
            },
        }

    def catalog(self, query: str, limit: int = 20) -> dict[str, Any]:
        if not isinstance(query, str):
            raise LookupContractError("catalog query must be a string")
        needle_raw = query.strip()
        if (
            not needle_raw
            or len(needle_raw) > 64
            or "/" in needle_raw
            or "\\" in needle_raw
            or ".." in needle_raw
        ):
            raise LookupContractError("catalog query is invalid")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise LookupContractError("catalog limit is invalid")
        capped = min(limit, 50)
        needle = needle_raw.casefold()
        ranked: list[tuple[int, str, str, dict[str, Any]]] = []
        for entity_id, metadata in self._nodes.items():
            name_row = self._names.get(entity_id, {})
            display = name_row.get("display_name")
            hay = (display or "").casefold()
            exact_id = entity_id == needle_raw
            if needle not in hay and not exact_id:
                continue
            if hay == needle:
                rank = 0
            elif hay.startswith(needle):
                rank = 1
            elif needle in hay:
                rank = 2
            else:
                rank = 3
            ranked.append(
                (
                    rank,
                    display or "",
                    entity_id,
                    {
                        "entity_id": entity_id,
                        "display_name": display,
                        "name_conflict": bool(name_row.get("name_conflict", False)),
                        "role_group": metadata["role_group"],
                        "region": metadata["region"],
                    },
                )
            )
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        entities = [item[3] for item in ranked[:capped]]
        return {
            "query": needle_raw,
            "limit": capped,
            "match_count": len(entities),
            "truncated": len(ranked) > capped,
            "entities": entities,
        }

    def review_queue(self) -> dict[str, Any]:
        ranked: list[dict[str, Any]] = []
        for entity_id, row in self._service_rows.items():
            if row.get("role_group") != REVIEW_QUEUE_ROLE_GROUP:
                continue
            if row.get("insufficient_sample"):
                continue
            percentile = row.get("review_priority_percentile")
            if percentile is None:
                continue
            name_row = self._names.get(entity_id, {})
            node = self._nodes.get(entity_id, {})
            ranked.append({
                "entity_id": entity_id,
                "display_name": name_row.get("display_name"),
                "name_conflict": bool(name_row.get("name_conflict", False)),
                "role_group": REVIEW_QUEUE_ROLE_GROUP,
                "region": node.get("region"),
                "review_priority_percentile": float(percentile),
                "role_group_sample_size": int(row.get("role_group_sample_size") or 0),
            })
        ranked.sort(key=lambda item: (
            -item["review_priority_percentile"],
            item["display_name"] or "",
            item["entity_id"],
        ))
        entities = [{"rank": index, **item} for index, item in enumerate(ranked[:REVIEW_QUEUE_LIMIT], start=1)]
        return {
            "anchor_month": self.index.anchor_month,
            "window_months": list(self.index.window_months),
            "role_group": REVIEW_QUEUE_ROLE_GROUP,
            "limit": REVIEW_QUEUE_LIMIT,
            "eligible_count": len(ranked),
            "truncated": len(ranked) > REVIEW_QUEUE_LIMIT,
            "entities": entities,
        }
