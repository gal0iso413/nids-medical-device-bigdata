"""Local-only API over verified Class 2 serving marts."""

from .app import create_app, create_integrated_app

__all__ = ["create_app", "create_integrated_app"]
