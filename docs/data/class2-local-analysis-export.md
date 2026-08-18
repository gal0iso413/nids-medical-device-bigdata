# Class 2 local analysis export

This offline-only command reads only the requested monthly fact partitions, validates each selected partition manifest and checksum, filters the requested item-group or parent-scoped item-name selections, and writes the existing PR #15 serializer payload for PR #16's local adapter.

It does not start an API, read Excel, expose a database, or apply a public release/suppression policy. Every generated payload is marked `local_only`; `public_policy_state` and `suppression_policy_state` remain `not_applied` and `not_evaluated`.

## Configuration

Create an untracked JSON configuration outside the repository's generated directory:

```json
{
  "parquet_root": "C:/local/monthly-fact-store",
  "period_start": "202401",
  "period_end": "202403",
  "selections": [
    {"selection_type": "item_group", "label": "ITEM_GROUP_A"},
    {"selection_type": "item_name", "label": "ITEM_NAME_B", "parent_item_group_label": "ITEM_GROUP_B"}
  ]
}
```

An item-name selection always includes its parent item-group label. This prevents equal names under different groups from merging.

Run:

```powershell
python -m data_pipeline.offline.class2_analysis_export --config C:/local/class2-export-config.json
```

The command atomically publishes only these ignored files:

```text
web/class2_public/public/generated/class2-analysis.json
web/class2_public/public/generated/class2-analysis-manifest.json
```

The manifest records partition lineage, selection and period, fact/analysis/export contract versions, local-only policy state, and the generated JSON SHA-256. Identical inputs are `unchanged`; a different lineage or selection at the same destination is blocked instead of overwritten.

## Local web mode

The existing PR #16 adapter reads the default generated path without a URL override:

```powershell
$env:VITE_CLASS2_DATA_SOURCE = "local"
npm --prefix web/class2_public run dev
```

Or set `VITE_CLASS2_ANALYSIS_URL` to a separately hosted local JSON file. The browser reads JSON only; JSON generation remains this offline command's responsibility. `local` mode is not a public-service approval or release state.
