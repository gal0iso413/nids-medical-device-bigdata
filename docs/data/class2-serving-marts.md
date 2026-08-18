# Class 2 serving marts

`data_pipeline.analysis.class2_serving_mart` is an offline batch builder. It
creates immutable, query-oriented Parquet marts from a bounded period of
already verified PR-02 monthly facts. It is neither an Excel ingestion path nor
an HTTP/API service.

```powershell
python -m data_pipeline.analysis.class2_serving_mart `
  --fact-root "D:\NIDS Local Run\facts" `
  --output-root "D:\NIDS Local Run\class2-serving-marts"
```

`--period-start` / `--period-end` remain available to bound a rebuild. When both
are omitted, the mart covers every verified month currently in the fact root
(minimum through maximum). The Class 2 comparison UI is unchanged: the operator
still picks a start–end period of at most 36 months.

`python -m data_pipeline.cli.class2_serving_mart` is an equivalent standalone
CLI entrypoint; it does not alter the existing field-runner commands.

For Windows x64 CPython 3.13, install the project pipeline requirements and the
separate `tools/offline/requirements-class2-serving-mart-win-py313.lock` wheel
addition with `--no-index --require-hashes`. The immutable 43-wheel analysis-kit
lock is intentionally unchanged.

## Input and publication contract

Every requested `YYYYMM` partition is verified with the existing monthly-fact
manifest, schema, size, and SHA-256 verifier before it is read. The builder
never opens Excel, a checkpoint database, a scale-preflight report, or a raw
workbook. A missing, invalid, or unverified requested partition fails the run.

The output is atomically published at
`class2_serving_mart/schema_version=1.1.0`. A canonical `_manifest.json` records
only portable partition names, verified checksums, fact/schema versions, period,
output row counts/checksums, and a deterministic fingerprint. It contains no
absolute paths, usernames, machine names, or supplier/receiver identifiers.
Rebuilding identical input is `unchanged`; a different candidate at an existing
output path fails with a conflict rather than overwriting it.

The output root must not overlap the fact root or an operator-supplied checkpoint
root. Materialized Parquet and manifests are ignored by Git.

## Mart grains

| Mart | Grain | Notes |
| --- | --- | --- |
| `product_catalog` | `product_id × item_group_id × item_name_id` | Includes source months; item-name lookup is always parent (`item_group_id`) scoped. |
| `product_month` | `month × product_id` | Decimal sums remain Decimal. Supplier/receiver distincts are exact. UDI and active-day fields are explicitly upstream-cell sums because the monthly fact does not retain raw UDI/day identity. |
| `item_group_month` | `month × item_group_id` | Uses exact DuckDB `COUNT(DISTINCT)` over fact endpoint identifiers; it never sums product-level distincts. |
| `endpoint_composition` | `month × product_scope × endpoint × dimension × value` | `product_scope` is `product` or `item_group`; exact distinct counts and transaction counts are persisted—never source endpoint identifiers. |
| `endpoint_membership` | `month × product_scope × endpoint × entity_hash` | Hashed supplier/receiver membership for item-group and parent-scoped item-name grains. Used only to compute per-item HHI and set overlap; hashes are never returned by the query API. |
| `coverage` | `month` | Aggregate observations, additive measures, valid-row counts, endpoint-dimension valid transaction counts and coverage ratios, plus source quality flags. These are aggregate observations, not a claim that data are publicly publishable. |

DuckDB is an in-process batch aggregation dependency only. FastAPI, DuckDB HTTP,
query endpoints, public-serving policy, and the Class 2 React API-mode change are
outside this PR. The next serving/API layer must consume this manifest-verified
mart directory and must preserve the parent-scoped item-name and endpoint privacy
contracts above.
