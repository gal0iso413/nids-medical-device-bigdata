# Complete offline analysis kit

This directory builds a separate, immutable kit for the existing local analysis
contracts. It does not alter the older pipeline-only field kit. The builder is
run on an internet-connected preparation PC; every install, verification,
analysis, and localhost serving action in the resulting kit is offline.

Onsite operators (Wed 09:00–Thu 18:00, USB/망연계, no internet) should follow
the Korean [onsite operator playbook](../../docs/data/onsite-operator-playbook.md).
The published kit copies that file to `onsite-operator-playbook.md`. Use
`keep-session.ps1` around long commands, `run-analysis.ps1 -LogPath` for a
command transcript, and `status-analysis.ps1` to read checkpoint/fact/Class 1
manifests without reopening Excel or Parquet.

The runtime is CPython 3.13.12 Windows x64 and its single hash-locked
wheelhouse. `run-analysis.ps1` only delegates to the existing field runner,
Class 2 exporter, and Class 1 anchor runner. It contains no pipeline or model
implementation.

Both screens are internal localhost applications, not a public service.
After offline install:

1. Run the existing pipeline (`run-analysis.ps1 pipeline`). Company display
   names are captured in that same Excel ingest pass.
2. Optionally measure the Class 1 training graph with
   `run-class1-graph-scale-gate.ps1`.
3. Run GAD-NR for each of the latest six completed anchors (`run-analysis.ps1 class1-run` once per anchor config).
4. Build the Class 1 lookup index with `build-class1-lookup-index.ps1` once per those six anchors. The index is schema `1.2.0` with `_catalog.json` and `anchor_month=` partitions.
5. Build verified Class 2 serving marts with `build-class2-serving-marts.ps1`. Omit `-PeriodStart`/`-PeriodEnd` so the mart covers every verified fact month.
6. Serve the same screens as the local checkout:
   - Class 1 lookup API + React at `127.0.0.1:8011` (`serve-class1-site.ps1`)
   - Class 2 comparison API + React at `127.0.0.1:8012` (`serve-class2-site.ps1`)
   - or both with `serve-analysis-sites.ps1 -IndexRoot ... -MartRoot ...`

Status remains `local_internal_only` and `public_release_policy=not_approved`.
Class 1 reports `trains_on_request=false`. The kit includes FastAPI, DuckDB and
Uvicorn in the same hash-locked wheelhouse. Institutional approval,
authentication, audit, deployment, public-release suppression, and
differential-attack protection remain separate decisions.

## Preparation-PC React builds

Copy verified production builds into the kit. Class 1 must be API mode:

```powershell
cd web/class1_internal
$env:VITE_CLASS1_DATA_SOURCE = "api"
npm ci
npm run build

cd ../class2_public
$env:VITE_CLASS2_DATA_SOURCE = "api"
npm ci
npm run build
```

Do not publish generated analysis JSON into `sites/class1` or `sites/class2`.
The kit keeps those `generated/` directories empty. Lookup indexes and serving
marts stay outside the static roots.

## Site-PC sequence

Paths below are placeholders. Keep Excel, monthly facts, model output, lookup
indexes, and marts outside the kit. After the pipeline, build and serve Class 2
before GAD-NR. Do not run the pipeline and GAD-NR at the same time.

```powershell
.\keep-session.ps1 -LogPath C:\secure\logs\pipeline.log -File .\run-analysis.ps1 -ArgumentList @('-Command','preflight','-Config','C:\secure\field-run.toml')
.\keep-session.ps1 -LogPath C:\secure\logs\pipeline.log -File .\run-analysis.ps1 -ArgumentList @('-Command','pipeline','-Config','C:\secure\field-run.toml','-LogPath','C:\secure\logs\pipeline.cmd.log')
.\status-analysis.ps1 -Config C:\secure\field-run.toml -MartRoot C:\secure\class2-serving-marts
.\build-class2-serving-marts.ps1 -FieldRunConfig C:\secure\field-run.toml -FactRoot D:\nids\monthly-fact -OutputRoot C:\secure\class2-serving-marts
.\serve-class2-site.ps1 -MartRoot C:\secure\class2-serving-marts
.\run-class1-graph-scale-gate.ps1 -Config C:\secure\class1-graph-scale-gate.json -Report C:\secure\reports\class1-graph-scale-gate.json
.\run-analysis.ps1 -Command class1-run -Config C:\secure\field-run.toml -LogPath C:\secure\logs\class1.log
.\build-class1-lookup-index.ps1 -FactRoot D:\nids\monthly-fact -RunRoot C:\secure\class1-offline-anchor -OutputRoot C:\secure\class1-lookup-index -AnchorMonth 202403
.\serve-analysis-sites.ps1 -IndexRoot C:\secure\class1-lookup-index -MartRoot C:\secure\class2-serving-marts
```

Excel, monthly facts, model scores, and site-specific configuration are not
shipped in the kit.
