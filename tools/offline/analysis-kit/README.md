# Complete offline analysis kit

This directory builds a separate, immutable kit for the existing local analysis
contracts. It does not alter the older pipeline-only field kit. The builder is
run on an internet-connected preparation PC; every install, verification,
analysis, and static-site serving action in the resulting kit is offline.

The runtime is CPython 3.13.12 Windows x64 and its single hash-locked
wheelhouse. `run-analysis.ps1` only delegates to the existing field runner,
Class 3 exporter, Class 1 anchor runner, and Class 1 safe handoff publisher.
It contains no pipeline or model implementation.

The Class 3 site is an internal localhost application, not a public service.
After offline install: run the existing pipeline, build verified serving marts
with `build-class3-serving-marts.ps1`, then run `serve-class3-site.ps1` with
`-Host 127.0.0.1`. It serves React at `/` and the fixed API at `/api`; status
remains `local_internal_only` and `public_release_policy=not_approved`. The
kit includes FastAPI, DuckDB and Uvicorn in the same hash-locked wheelhouse.
Institutional approval, authentication, audit, deployment, and differential
attack protection remain separate decisions.
