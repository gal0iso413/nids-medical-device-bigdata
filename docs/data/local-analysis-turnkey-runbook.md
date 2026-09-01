# Local analysis turnkey runbook

This is the supported local/internal workflow. It composes verified monthly
Parquet, the Class 2 exporter, the Class 1 GAD-NR anchor runner, and the React
adapters. It is not a public-service release. Do not commit Excel, Parquet,
SQLite, generated JSON, model results, or site-specific configuration.

## Choose an execution route

Run directly in this Cursor checkout when the approved local Python environment
is already available. Use the [offline analysis kit](../../tools/offline/analysis-kit/README.md)
when moving the workflow to another PC; its installer verifies the exact wheel
set before creating an isolated environment. Onsite USB operation uses the
[onsite operator playbook](onsite-operator-playbook.md). The kit serves Class 1
through the localhost lookup API (`127.0.0.1:8011`) and Class 2 through the
localhost comparison API (`127.0.0.1:8012`). It does not publish generated JSON
into the static site roots.

Do not use removed Class 1 graph/Excel/model-comparison commands or any
Streamlit entrypoint. The only Class 1 runtime entrypoint is
`class_1_anomaly_detection.src.offline_anchor_runner`.

## Separate configuration

Keep configuration outside the repository. The paths and identifiers below are
placeholders. Supply files use the dekade pattern
`공급내역보고자료(YYYYMMDD~YYYYMMDD).xlsx`; the field runner publishes only
months with exactly three files. Changing the master lookup does not re-join
already closed months.

```json
{"parquet_root":"D:/nids/monthly-fact","selections":[{"selection_type":"item_group","label":"ITEM_GROUP"}],"web_public_root":"C:/workspace/web/class2_public/public"}
```

```json
{"parquet_root":"D:/nids/monthly-fact","output_root":"C:/workspace/class_1_anomaly_detection/output/offline-anchor","anchor_month":"202403","selected_entity_id":"internal-entity-id","region_vocabulary":["11","26"],"model_version":"gadnr-internal-1","seed":17,"minimum_role_sample":30}
```

`region_vocabulary` must be explicit, sorted, and unique. Class 1 output must
be separate from the Parquet root; restricted QA output is never static web
data. Class 1 completion is the latest **six** precomputed GAD-NR anchors.
Each anchor `M` reads Parquet `M-5` through `M`, so those six anchors need the
latest 11 closed months on disk. Do not slice the training graph if the scale
gate fails.

## Direct Cursor execution

```powershell
python -m data_pipeline.cli preflight --config C:/secure/data-preparation.json
python -m data_pipeline.cli run --config C:/secure/data-preparation.json
python -m data_pipeline.offline.local_analysis_tools inventory --parquet-root D:/nids/monthly-fact --limit 20
python -m data_pipeline.offline.class2_analysis_export --config C:/secure/class2-export.json
python -m data_pipeline.observability.class1_graph_scale_gate --config C:/secure/class1-graph-scale-gate.json --report C:/secure/reports/class1-graph-scale-gate.json
python -m class_1_anomaly_detection.src.offline_anchor_runner --config C:/secure/class1-anchor.json
python -m data_pipeline.ingest.company_display_name --supply-workbooks C:/secure/inputs/공급내역보고자료(20240301~20240310).xlsx --output-root D:/nids/monthly-fact
python -m data_pipeline.analysis.class1_lookup_index --fact-root D:/nids/monthly-fact --run-root C:/workspace/class_1_anomaly_detection/output/offline-anchor --output-root C:/secure/class1-lookup-index --anchor-month 202403
python -m data_pipeline.offline.local_analysis_tools verify-class1 --output-root C:/workspace/class_1_anomaly_detection/output/offline-anchor --anchor-month 202403
python -m data_pipeline.offline.local_analysis_tools publish-class1-web --output-root C:/workspace/class_1_anomaly_detection/output/offline-anchor --web-public-root C:/workspace/web/class1_internal/public --anchor-month 202403
python -m data_pipeline.offline.local_analysis_tools verify-class1-web --web-public-root C:/workspace/web/class1_internal/public --anchor-month 202403 --selected-entity-id internal-entity-id
python -m data_pipeline.offline.local_analysis_tools verify-class2 --web-public-root C:/workspace/web/class2_public/public
```

Verification is read-only. Class 2 verifies the canonical payload and manifest.
Class 1 permits only `completed` or `insufficient_graph`, rejects raw scores in
the web JSON, and blocks restricted output below `web/public/generated`.

## React adapters

```powershell
$env:VITE_CLASS2_DATA_SOURCE = "local"
npm --prefix web/class2_public run dev

$env:VITE_CLASS1_DATA_SOURCE = "local"
$env:VITE_CLASS1_HANDOFF_URL = "/generated/class1-current.json"
npm --prefix web/class1_internal run dev

$env:VITE_CLASS1_DATA_SOURCE = "api"
npm --prefix web/class1_internal run dev
```

Neither adapter falls back to mock data after a local load fails. Field-data
validation must use approved storage, memory, recovery, data-quality, and
access controls; its result is not production or public approval.
