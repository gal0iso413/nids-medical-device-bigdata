# Local analysis turnkey runbook

This is the supported local/internal workflow. It composes verified monthly
Parquet, the Class 3 exporter, the Class 1 GAD-NR anchor runner, and the React
adapters. It is not a public-service release. Do not commit Excel, Parquet,
SQLite, generated JSON, model results, or site-specific configuration.

## Choose an execution route

Run directly in this Cursor checkout when the approved local Python environment
is already available. Use the [offline analysis kit](../../tools/offline/analysis-kit/README.md)
when moving the workflow to another PC; its installer verifies the exact wheel
set before creating an isolated environment.

Do not use removed Class 1 graph/Excel/model-comparison commands or any
Streamlit entrypoint. The only Class 1 runtime entrypoint is
`class_1_anomaly_detection.src.offline_anchor_runner`.

## Separate configuration

Keep configuration outside the repository. The paths and identifiers below are
placeholders.

```json
{"parquet_root":"D:/nids/monthly-fact","period_start":"202401","period_end":"202403","selections":[{"selection_type":"item_group","label":"ITEM_GROUP"}],"web_public_root":"C:/workspace/web/class3_public/public"}
```

```json
{"parquet_root":"D:/nids/monthly-fact","output_root":"C:/workspace/class_1_anomaly_detection/output/offline-anchor","anchor_month":"202403","selected_entity_id":"internal-entity-id","region_vocabulary":["11","26"],"model_version":"gadnr-internal-1","seed":17,"minimum_role_sample":30}
```

`region_vocabulary` must be explicit, sorted, and unique. Class 1 output must
be separate from the Parquet root; restricted QA output is never static web
data.

## Direct Cursor execution

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

Verification is read-only. Class 3 verifies the canonical payload and manifest.
Class 1 permits only `completed` or `insufficient_graph`, rejects raw scores in
the web JSON, and blocks restricted output below `web/public/generated`.

## React adapters

```powershell
$env:VITE_CLASS3_DATA_SOURCE = "local"
npm --prefix web/class3_public run dev

$env:VITE_CLASS1_DATA_SOURCE = "local"
$env:VITE_CLASS1_HANDOFF_URL = "/generated/class1-current.json"
npm --prefix web/class1_internal run dev
```

Neither adapter falls back to mock data after a local load fails. Field-data
validation must use approved storage, memory, recovery, data-quality, and
access controls; its result is not production or public approval.
