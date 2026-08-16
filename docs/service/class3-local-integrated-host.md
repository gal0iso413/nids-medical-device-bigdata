# Class 3 local integrated host

This localhost-only host serves a verified Class 3 React production build and
the manifest-verified local API from one origin. It is not public deployment,
authentication, or release approval.

```powershell
cd web/class3_public
npm ci
npm run build

python -m services.class3_local_api `
  --mart-root "D:\NIDS Local Run\class3-serving-marts" `
  --static-root "D:\NIDS Local Run\class3-web-dist" `
  --host 127.0.0.1 `
  --port 8013
```

For field use, copy the verified production build to the external static-root
path; do not serve the source tree's `dist` directory directly from an offline
kit. The default and documented host is loopback only. CORS is not enabled.

`GET /` and non-`/api` deep links return the React index. `GET /api/healthz`
and `GET /api/v1/status` remain API endpoints. The status remains
`local_internal_only` with `public_release_policy=not_approved`; this is not
public release or completed authentication.

Startup rejects absent roots or indexes, static/mart root overlap, paths that
escape the static root, and static data artifacts including manifests, Parquet,
Excel, checkpoints, generated artifacts, and JSON. It also rejects literal raw
endpoint values or absolute filesystem paths in the served build. It never
serves mart files or absorbs `/api` requests into SPA fallback.
