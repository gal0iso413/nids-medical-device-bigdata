"""Run the Class 2 API only on a local loopback interface."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .app import create_app, create_integrated_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local-only Class 2 query API.")
    parser.add_argument("--mart-root", required=True, type=Path)
    parser.add_argument("--static-root", type=Path, help="verified React production build directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8012, type=int)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("only loopback hosts are permitted for this local-only API")
    app = create_app(args.mart_root) if args.static_root is None else create_integrated_app(args.mart_root, args.static_root)
    uvicorn.run(app, host=args.host, port=args.port, workers=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
