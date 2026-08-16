# Class 1 offline anchor analysis

Class 1 consumes verified monthly Parquet and runs GAD-NR for one selected
entity and anchor month. The supported execution entrypoint is:

```powershell
python -m class_1_anomaly_detection.src.offline_anchor_runner --config <config>
```

The runner returns `completed` when the selected graph is sufficient and
`insufficient_graph` when it is not. Restricted QA output and the safe web
JSON handoff are separate artifacts: restricted material must never be copied
to the static site.

Follow the [local analysis turnkey runbook](../docs/data/local-analysis-turnkey-runbook.md)
for configuration, verification, and the React handoff sequence. The React
interface is under [`web/class1_internal/`](../web/class1_internal/).

The active model path is GAD-NR only. Do not substitute a legacy graph, Excel
loader, or model-comparison entrypoint.
