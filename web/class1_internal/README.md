# Class 1 internal local monitor

React 19, Vite 8, and TypeScript strict internal-only viewer. It reads only the
offline runner's `internal-service.json` and `internal-one-hop-graph.json`;
the browser never reads Excel, Parquet, or SQLite.

Use Node `^20.19.0 || ^22.12.0 || >=24.0.0` and npm `>=10`.

```powershell
npm ci
$env:VITE_CLASS1_DATA_SOURCE = "local"
$env:VITE_CLASS1_SERVICE_URL = "/generated/internal-service.json"
$env:VITE_CLASS1_GRAPH_URL = "/generated/internal-one-hop-graph.json"
npm run dev
```

The generated files belong under `public/generated/` and are ignored. The
offline runner creates the JSON; this app does not create or modify it. Local
analysis is internal-only and does not indicate a public release or approval.
Missing URLs, loading failures, invalid payloads, and service/graph entity
mismatches show an error and never fall back to mock data. Development fixtures,
when used in tests, stay under `src/mock/` and are not imported by the runtime
local adapter or production build.

For the end-to-end offline sequence and artifact verification, see
[`docs/data/local-analysis-turnkey-runbook.md`](../../docs/data/local-analysis-turnkey-runbook.md).
