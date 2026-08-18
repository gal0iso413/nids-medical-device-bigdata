"""Local-only lookup API over a verified Class 1 GAD-NR index."""

from typing import Any

__all__ = ["create_app", "create_integrated_app"]


def __getattr__(name: str) -> Any:
    if name in {"create_app", "create_integrated_app"}:
        from .app import create_app, create_integrated_app
        return create_app if name == "create_app" else create_integrated_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
