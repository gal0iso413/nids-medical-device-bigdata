# Class 1 graph-scale gate

`data_pipeline.observability.class1_graph_scale_gate` measures whether the
unsliced 3-month company-pair training graph can run GAD-NR on the current
machine. It is not an API, serving path, or permission to publish a search
index.

Copy [`config/class1-graph-scale-gate.example.json`](../../config/class1-graph-scale-gate.example.json)
outside the repository and replace the placeholder paths and ceilings. The
live config, monthly facts, and report must stay outside the repository.

```powershell
python -m data_pipeline.observability.class1_graph_scale_gate `
  --config C:/secure/class1-graph-scale-gate.json `
  --report C:/secure/reports/class1-graph-scale-gate.json
```

The gate reads the same six checksum-verified monthly partitions the offline
anchor runner requires (anchor minus five through the anchor). It then builds
the same 3-month model graph used by GAD-NR, records node and edge counts,
peak process RSS, Python allocation peak, and GAD-NR wall time.

Failure does not authorize slicing that training graph by region or item
group. If node or edge counts exceed the configured ceilings, GAD-NR is
skipped and the report fails closed.

The report contains only aggregate counts, timings, ceilings, and
non-identifying environment facts. It excludes absolute paths, company or
product identifiers, and selected-entity IDs. `tracemalloc_peak_bytes` covers
Python allocations only; it is not total native process memory.

This measurement is for the facts currently on disk. Repeat it when a larger
production extract is ingested. Do not slice the training graph by region or
item group if that later measurement fails.
