# Class 1 batch handoff schemas (next-year system linkage prep)

> Not a live API. Batch CSV/Parquet column contracts for exporting review outputs
> into NIDS integrated information systems later.

## Files

| Artifact | Purpose |
|----------|---------|
| `entity_review_scores.header.csv` | Per-entity GAD-NR score + auxiliary evidence |
| `anchor_manifest.header.csv` | One row per scored anchor window |

## Conventions

- Encoding: UTF-8 with BOM for CSV handoff samples
- `anchor_month`: YYYYMM
- `model_slug`: production default `gadnr`
- Scores are **internal reference**; `disclaimer_code` always `INTERNAL_MONITORING_ONLY`

## entity_review_scores columns

See `entity_review_scores.header.csv.example`.

## Update policy

Changing columns requires a PM note in `shared_docs/structured/class_1_anomaly_spec.md`.
