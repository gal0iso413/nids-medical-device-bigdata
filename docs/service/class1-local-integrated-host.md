# Class 1 local integrated host

This localhost-only host serves a verified Class 1 React production build and
the lookup API from one origin. It is not public deployment, authentication,
or release approval. It does not train GAD-NR on request.

```powershell
cd web/class1_internal
$env:VITE_CLASS1_DATA_SOURCE = "api"
npm ci
npm run build

python -m services.class1_local_api `
  --index-root "D:\NIDS Local Run\class1-lookup-index" `
  --static-root "D:\NIDS Local Run\class1-web-dist" `
  --host 127.0.0.1 `
  --port 8011
```

For field use, copy the verified API-mode production build to the external
static-root path; do not serve the source tree's `dist` directory directly
from an offline kit. The default and documented host is loopback only. CORS
is not enabled.

`GET /` and non-`/api` deep links return the React index. `GET /api/healthz`,
`GET /api/v1/status`, `GET /api/v1/review-queue`, and the bounded name catalog
remain API endpoints. Status remains `local_internal_only` with
`public_release_policy=not_approved` and `trains_on_request=false`.

Startup rejects absent roots or indexes, static/index root overlap, paths that
escape the static root, and static data artifacts including manifests, Parquet,
Excel, checkpoints, generated artifacts, and JSON. It also rejects literal raw
endpoint values or absolute filesystem paths in the served build. It never
serves lookup-index files or absorbs `/api` requests into SPA fallback.

The offline analysis kit uses `serve-class1-site.ps1` with the same contract.
