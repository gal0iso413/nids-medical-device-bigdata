# Class 1 offline anchor runner

The runner reads six already-published, checksum-verified monthly fact Parquet
partitions and runs the existing PR #17 GAD-NR contract for one anchor month.
It is an internal/local operation, not a public release workflow.

Create a config outside the repository (paths below are examples):

```json
{
  "parquet_root": "D:/nids/monthly-fact",
  "output_root": "C:/Users/example/Documents/Projects/NIDS/cursor/class_1_anomaly_detection/output/offline-anchor",
  "anchor_month": "202406",
  "region_vocabulary": ["11", "26"],
  "model_version": "gadnr-internal-1",
  "seed": 17,
  "minimum_role_sample": 30
}
```

Run it with:

```powershell
python -m class_1_anomaly_detection.src.offline_anchor_runner --config C:/secure/class1-anchor.json
```

`region_vocabulary` is mandatory and must be sorted and unique; the runner
never derives it in a production run. `output_root` must be separate from,
and not nested inside, `parquet_root`. The runner requires all months from
anchor minus five through the anchor itself to pass full checksum verification.

It writes only ignored, internal artifacts below `output_root/anchor_month=…`:
`restricted-qa.json` contains raw scores and review evidence; `internal-service.json`
uses the existing Class 1 service serializer and has no raw score; and
`run-manifest.json` records relative source lineage, checksums, configuration,
fingerprints, output hashes, and its local/internal-only scope. Repeating the
same run is unchanged. Different input lineage, configuration, or content for
an existing anchor is blocked rather than overwritten.

If the graph is below configured node or edge thresholds, no score is produced;
the service-safe result reports `insufficient_graph`. PyGOD and torch remain
optional: the runner does not install them and reports an explicit optional-ML
dependency error when they are unavailable.
