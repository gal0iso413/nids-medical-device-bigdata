# Class 1 local lookup API

`services.class1_local_api` is a localhost lookup over a verified Class 1
index. It is not a public API, search service, SSO deployment, or permission
to train GAD-NR on request.

Build the index from a **completed** offline-anchor run and the same verified
monthly facts. The index stores every graph entity's service row plus the
unsliced company-pair edges so any entity can be looked up without rerunning
the model.

```powershell
python -m data_pipeline.analysis.class1_lookup_index `
  --fact-root D:/nids/monthly-fact `
  --run-root C:/secure/class1-offline-anchor `
  --output-root C:/secure/class1-lookup-index `
  --anchor-month 202403

python -m services.class1_local_api `
  --index-root C:/secure/class1-lookup-index `
  --host 127.0.0.1 `
  --port 8011
```

Only loopback hosts are accepted. CORS, SSO, internet exposure, and
multi-worker deployment are intentionally absent. The internal screen opens on the distributor review queue, then searches
by Korean company name through the bounded catalog.

## Contract

- `GET /healthz` reports `local_internal_only` and the verified catalog fingerprint.
- `GET /v1/status` reports `available_anchor_months`, `default_anchor_month`
  (latest completed), the default anchor's window and entity/edge counts,
  `trains_on_request=false`, and the fixed review-queue role/limit.
- Lookup endpoints accept `?anchor_month=YYYYMM`. Omitting the query uses the
  latest completed partition. A missing, future, or malformed month is **422**.
  A month that exists but does not contain the entity is **404**.
- `GET /v1/review-queue` returns that anchor's top 10 **distributor**
  entities by GAD-NR role-group percentile. The role group is `distributor`
  only, including supply `업종` `판매(임대)업`. Ranked rows never include
  `raw_score`. Firms below the role-group sample minimum are omitted rather
  than shown as a ranked review target.
- `GET /v1/catalog/entities?q=&limit=` returns a bounded Korean display-name
  catalog for that anchor (default 20, max 50). Duplicate names return multiple hits with role
  and region. A missing name is omitted from name match rather than invented.
- `GET /v1/entities/{entity_id}` returns that entity's service allow-list row.
- `GET /v1/entities/{entity_id}/relationships` returns the UI 1-hop graph,
  including `display_name` on each node when the name directory was joined.

The index is schema `1.2.0`:

```text
{output_root}/class1_lookup_index/schema_version=1.2.0/
  _catalog.json
  anchor_month=YYYYMM/
```

Only the requested month's partition is loaded into memory. There is no unbounded `?query=` search, no global 2-hop, and no raw GAD-NR
score. The service never opens Excel, monthly facts, or
`restricted-qa.json`. Display names come from the ingest side-channel documented
in [`company-display-name.md`](../data/company-display-name.md).

React API mode uses the same 1-hop screen as local JSON mode. The Vite
dev server proxies `/api/*` to the lookup API after stripping the `/api`
prefix, because the standalone service serves `/v1/status` rather than
`/api/v1/status`.

```powershell
$env:VITE_CLASS1_DATA_SOURCE = "api"
npm --prefix web/class1_internal run dev -- --host 127.0.0.1 --port 5174
```

The offline analysis kit serves this API with the React production build
through [`class1-local-integrated-host.md`](class1-local-integrated-host.md)
and `serve-class1-site.ps1`. That host is loopback only.

Before any authenticated internal service, approval is required for SSO/RBAC,
audit logging, and deployment configuration.
