"""Strict TOML configuration contract for the offline field runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Any, Final


CONFIG_VERSION: Final = "1.1.0"
_HEX_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")


class FieldRunConfigError(ValueError):
    """Raised when a field-run TOML document violates the local contract."""


@dataclass(frozen=True)
class FieldRunConfig:
    config_path: Path
    supply_workbooks: tuple[Path, ...]
    master_lookup_root: Path
    master_source_hash: str | None
    master_workbooks: tuple[Path, ...]
    checkpoint_root: Path
    output_root: Path
    batch_size: int
    max_month_fact_bytes: int
    minimum_free_bytes: int

    @property
    def uses_master_workbooks(self) -> bool:
        return bool(self.master_workbooks)


def _require_table(document: dict[str, Any], name: str) -> dict[str, Any]:
    value = document.get(name)
    if not isinstance(value, dict):
        raise FieldRunConfigError(f"[{name}] must be a TOML table")
    return value


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise FieldRunConfigError(
            f"{label} contains unsupported fields: {', '.join(unknown[:20])}"
        )


def _path(value: Any, *, base: Path, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise FieldRunConfigError(f"{field} must be a non-empty path string")
    candidate = Path(value.strip())
    return candidate if candidate.is_absolute() else base / candidate


def _paths(value: Any, *, base: Path, field: str) -> tuple[Path, ...]:
    if not isinstance(value, list) or not value:
        raise FieldRunConfigError(f"{field} must be a non-empty path array")
    paths = tuple(_path(item, base=base, field=field) for item in value)
    normalized = [str(path.resolve(strict=False)).casefold() for path in paths]
    if len(set(normalized)) != len(normalized):
        raise FieldRunConfigError(f"{field} must not contain duplicate paths")
    return paths


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise FieldRunConfigError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FieldRunConfigError(f"{field} must be a nonnegative integer")
    return value


def load_field_run_config(config_path: Path) -> FieldRunConfig:
    """Load a strict config, resolving relative paths beside the TOML file."""

    if not isinstance(config_path, Path):
        raise TypeError("config_path must be pathlib.Path")
    try:
        raw = config_path.read_bytes()
    except OSError as exc:
        raise FieldRunConfigError("Could not read the field-run config") from exc
    try:
        document = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise FieldRunConfigError("Field-run config is not valid UTF-8 TOML") from exc
    if not isinstance(document, dict):
        raise FieldRunConfigError("Field-run config root must be a TOML table")
    _reject_unknown(document, {"config_version", "paths", "master", "run"}, "config")
    if document.get("config_version") != CONFIG_VERSION:
        raise FieldRunConfigError(f"config_version must be {CONFIG_VERSION}")

    paths = _require_table(document, "paths")
    master = _require_table(document, "master")
    run = _require_table(document, "run")
    _reject_unknown(
        paths,
        {"supply_workbooks", "checkpoint_root", "output_root"},
        "[paths]",
    )
    _reject_unknown(
        master,
        {"lookup_root", "source_hash", "workbooks"},
        "[master]",
    )
    _reject_unknown(
        run,
        {"batch_size", "max_month_fact_bytes", "minimum_free_bytes"},
        "[run]",
    )

    base = config_path.parent
    source_hash = master.get("source_hash")
    workbook_values = master.get("workbooks")
    if (source_hash is None) == (workbook_values is None):
        raise FieldRunConfigError(
            "[master] must define exactly one of source_hash or workbooks"
        )
    if source_hash is not None and (
        not isinstance(source_hash, str) or _HEX_PATTERN.fullmatch(source_hash) is None
    ):
        raise FieldRunConfigError("master.source_hash must be 64 lowercase hex characters")
    master_workbooks = (
        _paths(workbook_values, base=base, field="master.workbooks")
        if workbook_values is not None
        else ()
    )
    return FieldRunConfig(
        config_path=config_path,
        supply_workbooks=_paths(
            paths.get("supply_workbooks"), base=base, field="paths.supply_workbooks"
        ),
        master_lookup_root=_path(
            master.get("lookup_root"), base=base, field="master.lookup_root"
        ),
        master_source_hash=source_hash,
        master_workbooks=master_workbooks,
        checkpoint_root=_path(
            paths.get("checkpoint_root"), base=base, field="paths.checkpoint_root"
        ),
        output_root=_path(
            paths.get("output_root"), base=base, field="paths.output_root"
        ),
        batch_size=_positive_int(run.get("batch_size"), "run.batch_size"),
        max_month_fact_bytes=_positive_int(
            run.get("max_month_fact_bytes"), "run.max_month_fact_bytes"
        ),
        minimum_free_bytes=_nonnegative_int(
            run.get("minimum_free_bytes", 0), "run.minimum_free_bytes"
        ),
    )
