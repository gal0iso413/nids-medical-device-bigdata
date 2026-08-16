# Scale readiness preflight

`data_pipeline.observability.scale_preflight` is a bounded, read-only sample
diagnostic. It is not a full ingest, master build, 3-key join, checkpoint, or
Parquet publication, and it never calculates a full workbook SHA-256.

Create the JSON configuration and report directory outside the repository.
Copy [`config/scale-preflight.example.json`](../../config/scale-preflight.example.json)
to an approved local location and replace its example paths.

```powershell
python -m data_pipeline.observability.scale_preflight `
  --config "D:\NIDS Local Run\scale-preflight.json" `
  --report "D:\NIDS Local Run\reports\scale-preflight.json"
```

The report contains only aggregate observations: ordinal workbook selection,
byte counts, row accounting, rejection counters, throughput, DataFrame deep
memory, Python allocation peak, and non-identifying environment facts. It
excludes absolute paths, user and computer names, workbook names, raw rows, and
transaction or product identifiers. `tracemalloc_peak_bytes` covers Python
allocations only; it is not total native process memory.

## Sampling and ETA

Use at most a representative ten-day file or one representative month onsite.
The optional 207-million-row value is divided by observed emitted rows/second
as a simple linear sample extrapolation. It does **not** establish a complete
2.07e8-row ETA, throughput SLA, or permission to start full ingest.

Before a full run, review observed throughput, disk growth rate, adapter
rejection ratio, monthly fact cardinality, and Class 1 nationwide graph node
and edge counts. This PR does not decide Class 1 GAD-NR feasibility; decide it
in a graph-scale gate after monthly Parquet exists. API and DuckDB work belong
to a later Class 3 serving-mart/API PR.
