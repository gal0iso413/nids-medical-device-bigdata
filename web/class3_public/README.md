# Class 3 local analysis React interface

This Vite/React interface reads a local analysis JSON payload produced by
`data_pipeline.offline.class3_analysis_export`. It never reads Excel, Parquet,
or SQLite in the browser.

For the end-to-end local workflow, use the
[local analysis turnkey runbook](../../docs/data/local-analysis-turnkey-runbook.md).
For a portable offline installation, use the
[analysis-kit README](../../tools/offline/analysis-kit/README.md).

## Development and validation

```powershell
npm ci
npm run typecheck
npm test
npm run build
```

Use local analysis mode with a generated payload only after the exporter has
completed and its manifest has been verified:

```powershell
$env:VITE_CLASS3_DATA_SOURCE = "local"
$env:VITE_CLASS3_ANALYSIS_URL = "/generated/class3-analysis.json"
npm run dev
```

Mock fixtures are development-test-only. They are not a fallback for a failed
local load and are not production or public approval. The former Streamlit,
MCDM/Kraljic, and prototype runtime paths have been removed from the current
tree; Git history remains the recovery mechanism for that historical code.
