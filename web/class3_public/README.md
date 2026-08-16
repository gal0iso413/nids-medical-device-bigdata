# Class 3 local analysis React interface

This Vite/React interface never reads Excel, Parquet, or SQLite in the browser.
It can load a verified local analysis JSON payload, a development-only mock
fixture, or the localhost Class 3 query API.

For the end-to-end local workflow, use the
[local analysis turnkey runbook](../../docs/data/local-analysis-turnkey-runbook.md).
For a portable offline installation, use the
[analysis-kit README](../../tools/offline/analysis-kit/README.md).
For the localhost integrated host, see
[Class 3 local integrated host](../../docs/service/class3-local-integrated-host.md).

## Development and validation

```powershell
npm ci
npm run typecheck
npm test
npm run build
```

The default development server shows an unconnected service-data state.

```powershell
npm run dev
```

## Local API mode

`VITE_CLASS3_DATA_SOURCE=api` selects the local Class 3 query API with the
same-origin `/api` base path. API mode verifies `/api/v1/status` first and does
not fall back to mock fixtures or local JSON when the API is unavailable or
rejects a request. The UI displays `local_internal_only` and
`public_release_policy=not_approved`; it is not a public service or release.

For local development only, Vite proxies `/api` to `127.0.0.1:8013`. The proxy
is development-server configuration and is not included in the production
bundle.

```powershell
python -m services.class3_local_api `
  --mart-root "D:\NIDS Local Run\class3-serving-marts" `
  --host 127.0.0.1 `
  --port 8013
```

```powershell
cd web/class3_public
$env:VITE_CLASS3_DATA_SOURCE = "api"
npm run dev
```

## Local analysis JSON

Use local analysis mode only after the exporter has completed and its manifest
has been verified:

```powershell
$env:VITE_CLASS3_DATA_SOURCE = "local"
$env:VITE_CLASS3_ANALYSIS_URL = "/generated/class3-analysis.json"
npm run dev
```

## Development mock

Mock fixtures are development-test-only. They are not a fallback for a failed
local or API load and are not production or public approval.

```powershell
$env:VITE_CLASS3_DATA_SOURCE = "mock"
$env:VITE_CLASS3_MOCK_FIXTURE = "released"
npm run dev
```

The former Streamlit, MCDM/Kraljic, and prototype runtime paths have been
removed from the current tree; Git history remains the recovery mechanism for
that historical code.
