# Class 3 local query API

This FastAPI + DuckDB service is strictly for localhost internal verification.
It is not a public API, external hosting deployment, authentication-complete
service, or a release approval.

```powershell
python -m services.class3_local_api `
  --mart-root "D:\NIDS Local Run\class3-serving-marts" `
  --host 127.0.0.1 `
  --port 8013
```

Only loopback hosts are accepted. CORS, SSO, authentication, reverse proxies,
internet exposure, and multi-worker deployment are intentionally absent.

## Input and startup verification

The only input is the PR-28 Class 3 serving-mart directory. The service never
opens original Excel files, raw monthly facts, checkpoints, or arbitrary paths.
Before the application factory returns, it validates the canonical mart manifest,
schema version, deterministic fingerprint, allowlisted in-root output names,
every output SHA-256, and each output row count using DuckDB. Any failure blocks
startup.

DuckDB is used only for fixed read queries over allowlisted mart files. Requests
cannot provide SQL, table names, file paths, or DuckDB options. Decimal measures
are returned as JSON strings, never JSON numbers.

## Local API contract

- `GET /healthz` reports `local_internal_only` health and the verified mart fingerprint.
- `GET /v1/status` reports the verified period and `public_release_policy=not_approved`.
- `GET /v1/catalog/item-groups?q=&limit=` provides bounded autocomplete (default 20, maximum 50).
- `GET /v1/catalog/item-names?item_group_id=&q=&limit=` requires the parent item group.
- `POST /v1/comparisons` accepts at most 10 item-group or parent-scoped item-name selections and a verified period of at most 36 months.

Responses contain product/group trends, endpoint compositions, coverage,
per-item supplier HHI, and selection-set overlap counts only; they never expose
raw source supplier or receiver identifiers or membership hashes.

## Dependencies and next steps

`requirements-class3-api.txt` pins DuckDB 1.5.5, FastAPI 0.141.1, and Uvicorn
0.52.3. The combination was installed from Windows x64 CPython 3.13 wheels.
The immutable offline analysis-kit lock is deliberately not modified; a future
kit refresh must add and verify the API dependency closure separately.

Before any public service, approval is required for public-release suppression,
authentication/authorization, audit controls, deployment configuration, and
offline-kit refresh. The next PR may add API mode to Class 3 React's existing
local JSON mode; this service does not modify the React application.
