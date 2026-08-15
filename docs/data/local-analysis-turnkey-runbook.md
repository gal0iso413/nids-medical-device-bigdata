# Local analysis turnkey runbook

This is an offline, local/internal workflow. It composes the existing monthly
pipeline, Class 3 exporter, Class 1 anchor runner, and React adapters. It is
not a public-service release, API, or field kit. Do not commit Excel, Parquet,
SQLite, generated JSON, or site-specific configuration.

## Separate untracked configuration

Keep three JSON files outside the repository. Paths and identifiers below are
placeholders only. Data preparation uses the existing [field runner](field-runner.md).

```json
{"parquet_root":"D:/nids/monthly-fact","period_start":"202401","period_end":"202403","selections":[{"selection_type":"item_group","label":"ITEM_GROUP"}],"web_public_root":"C:/workspace/web/class3_public/public"}
```

```json
{"parquet_root":"D:/nids/monthly-fact","output_root":"C:/workspace/class_1_anomaly_detection/output/offline-anchor","anchor_month":"202403","selected_entity_id":"internal-entity-id","region_vocabulary":["11","26"],"model_version":"gadnr-internal-1","seed":17,"minimum_role_sample":30}
```

`region_vocabulary` must be explicit, sorted, and unique. Class 1 output must
be separate from the Parquet root; restricted QA output is never web public data.

## Stepwise execution

Each command is independently runnable; do not run a later stage before its
input is available and checked.

```powershell
python -m data_pipeline.cli preflight --config C:/secure/data-preparation.json
python -m data_pipeline.cli run --config C:/secure/data-preparation.json
python -m data_pipeline.offline.local_analysis_tools inventory --parquet-root D:/nids/monthly-fact --limit 20
python -m data_pipeline.offline.class3_analysis_export --config C:/secure/class3-export.json
python -m class_1_anomaly_detection.src.offline_anchor_runner --config C:/secure/class1-anchor.json
python -m data_pipeline.offline.local_analysis_tools verify-class1 --output-root C:/workspace/class_1_anomaly_detection/output/offline-anchor --anchor-month 202403
python -m data_pipeline.offline.local_analysis_tools publish-class1-web --output-root C:/workspace/class_1_anomaly_detection/output/offline-anchor --web-public-root C:/workspace/web/class1_internal/public --anchor-month 202403
python -m data_pipeline.offline.local_analysis_tools verify-class1-web --web-public-root C:/workspace/web/class1_internal/public --anchor-month 202403 --selected-entity-id internal-entity-id
python -m data_pipeline.offline.local_analysis_tools verify-class3 --web-public-root C:/workspace/web/class3_public/public
```

Inventory projects only necessary Parquet columns and returns deterministic,
bounded JSON (`values` plus `omitted_count`). Item names retain parent group
scope. Entity IDs are analysis inputs, not an eligibility claim. It does not
print raw GAD-NR scores or row-level observations.

Verification is read-only. Class 3 checks canonical payload/manifest checksum,
schema, parent scope, and local-only status. Class 1 checks service/graph/
manifest identity and checksums, permits `completed`/`insufficient_graph`,
rejects raw scores in service/graph JSON, and blocks restricted output below
`web/public/generated`.

Class 1 web publication is the only bridge to the local React path. It first
verifies the external runner output, then atomically publishes only
`internal-service.json` and `internal-one-hop-graph.json` under
`web/class1_internal/public/generated/`, verifies those destination files, and
only then starts React. Restricted QA JSON and the source run manifest are
never copied. Source/destination nesting is blocked and identical publication
is reported as `unchanged`.

## Local web adapters

```powershell
$env:VITE_CLASS3_DATA_SOURCE = "local"
npm --prefix web/class3_public run dev

$env:VITE_CLASS1_DATA_SOURCE = "local"
$env:VITE_CLASS1_HANDOFF_URL = "/generated/class1-current.json"
npm --prefix web/class1_internal run dev
```

Neither adapter falls back to mock data after local loading fails. Local JSON
does not have public approval, release, or suppression-policy status. The real
Class 1 GAD-NR path still requires an approved local torch/PyGOD environment;
this runbook does not install wheels.

## Deferred to PR-24

Site packaging, timing/memory/file-lock field validation, and wider operator
field-kit UX are intentionally separate from this runbook.
