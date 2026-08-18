# Supply monthly checkpoint contract

Status: **Locked implementation contract for PR-03B2A**

Checkpoint contract version: `1.0.0`

This checkpoint connects a bounded, already normalized PR-03A supply batch to
the PR-01 monthly reducer after PR-03B1 has classified every row using the
immutable exact three-key master lookup. It does not open Excel, execute the
master join, publish Parquet, or expose service data.

## Public boundary

```python
create_or_open_supply_monthly_checkpoint(
    checkpoint_root,
    *,
    supply_lineage,
    master_verification,
)
```

```python
checkpoint.apply_classified_batch(batch, *, matched_mask)
checkpoint.verify_active()
checkpoint.seal(adapter_report=final_report, max_fact_bytes=512 * 1024 * 1024)
```

```python
verify_sealed_supply_checkpoint(checkpoint_root, run_id)
finalize_sealed_supply_checkpoint(checkpoint_root, run_id)
read_sealed_month_fact(
    checkpoint_root,
    run_id,
    month,
    *,
    max_fact_bytes,
)
```

The mask is positional and must cover the complete original PR-03A batch.
PR-03B1's bounded unmatched sample is diagnostic only; it cannot classify the
full batch. Every emitted normal row enters the ledger as `matched` or
`unmatched`, and only matched rows enter the accumulator. Rows rejected by the
adapter are represented only by the verified final `SupplyIngestionReport` at
EOF. The published `month` key is the dekade filename calendar month, not a
re-bin of `supply_date`. One checkpoint run is one closed month.

## Physical layout

```text
<checkpoint_root>/
  supply_monthly_orchestration/
    checkpoint_version=1.0.0/
      run_id=<64hex>/
        _run_manifest.json
        checkpoint.sqlite
        _sealed_manifest.json
```

The run manifest fixes supply and master lineage, contract versions, and the
fact-schema fingerprint. It contains no absolute path, machine name, user name,
attempt history, or batch boundary. The sealed manifest records the closed DB
checksum, row accounting, bounded unmatched diagnostics, months, grain counts,
and canonical fact fingerprints. Publication receipts and a complete manifest
belong to PR-03B2B.

## SQLite schema

- `run_metadata`: one run ID, one supply source version, `active|sealed`
- `source_row_ledger`: 32-byte source digest, 32-byte content digest, month,
  matched classification; `WITHOUT ROWID`
- `grain_accumulator`: additive Decimal/count and optional-dimension state at
  company×counterparty×product×month grain
- `grain_distinct_udi`: disk-backed distinct UDI state
- `grain_distinct_day`: disk-backed distinct active-day state
- `grain_quality_flag`: sorted, distinct upstream quality flags
- `sealed_summary`: one canonical summary and hash written only during seal;
  includes the final adapter report, SQL row counts, bounded diagnostics,
  month grain counts, and fact fingerprints

The run-scoped supply source version is stored once in `run_metadata`. A
validated `nids-row-v1:<64 lowercase hex>` ID is decoded losslessly into a
32-byte BLOB. The content digest covers every normalized source business field
except `source_version` and `source_row_id`. Equal digest/content/classification
is a replay no-op. Different content or classification is a conflict and rolls
back the complete classified batch.

## Transactions and recovery

This implementation is limited to one local writer:

- `journal_mode=WAL`
- `synchronous=NORMAL`
- `foreign_keys=ON`
- `BEGIN IMMEDIATE`
- one classified batch per commit

The immutable master join executes before this transaction. The checkpoint
transaction atomically confirms new ledger rows and all matched accumulator,
UDI/day, dimension, and quality state. Any error rolls it all back.

`synchronous=NORMAL` can lose the last committed WAL transaction after sudden
power loss. It cannot leave ledger and accumulator halves from the same
transaction. Active verification and deterministic replay from the immutable
source restore a lost tail. The module intentionally has no multi-writer lock
manager or concurrency retry policy.

## Transaction policy

The shared PR-01 policy is applied to the complete bounded batch before DB
mutation:

- `SUPPLY`: allowed
- `RETURN`/`RECALL`: `blocked:transaction_sign_policy_pending`
- `DISCARD`/`LEASE` and every other value:
  `blocked:transaction_type_unknown`
- negative forward amount/raw quantity/piece quantity:
  `blocked:negative_forward_value`

Unsupported rows are not silently excluded or converted to supply. Validated
piece quantity is preserved but never derived here. High supply amounts and
their upstream quality flags are preserved. This checkpoint contains source
facts; `amount_sum_clean` is not yet a disclosure-controlled public-service
metric.

## Seal and immutable read

Seal is allowed only after normal EOF with a validated final adapter report.
It blocks empty input, zero emitted rows, an empty ledger, all-unmatched input,
accounting mismatch, lineage mismatch, source conflict, or reducer invariant
failure. Months are never considered complete during streaming.

Each open checkpoint instance counts physical rows only after a classified
batch transaction commits. Replays and exact duplicates count toward this
session coverage; rolled-back batches do not. Seal requires that count to equal
the final adapter report's `rows_emitted`. Reopening a partial checkpoint
therefore requires replaying the immutable source from the beginning before it
can seal; ledger size is never used as a substitute for a complete source pass.

`max_fact_bytes` is mandatory for seal. Every month's accumulator grain count
is multiplied by the same conservative 4096-byte estimate used by the sealed
reader before any month DataFrame is restored. An exceeded bound leaves the DB
active and writes neither the sealed summary nor the sealed manifest, allowing
an explicit retry with a larger bound.

Seal restores one month at a time, validates it with the existing PR-01
contract, and creates the same canonical fact fingerprint as one-shot PR-01
aggregation. It then writes the canonical sealed summary and sealed state in
one transaction, commits, requires a non-busy `wal_checkpoint(TRUNCATE)`, closes
SQLite, confirms sidecar cleanup, and writes the canonical sealed manifest. It
does not run `VACUUM`.

The sealed summary and its hash are inside SQLite and therefore covered by the
closed database checksum. Manifest publication is a separate finalization
step. If manifest writing fails, the sealed DB remains immutable;
`finalize_sealed_supply_checkpoint()` opens it read-only and recreates only the
manifest. An identical manifest is a no-op and a different existing manifest
is a conflict. Finalization never replays source rows or changes accumulator
state. A run manifest left alone by an interrupted first initialization may
recreate its empty DB with the same lineage. An existing malformed DB is never
deleted or overwritten automatically.

After seal, SQLite and both manifests are immutable. The reader accepts only a
verified sealed checkpoint and restores one requested month. Before loading,
it applies a conservative `grain_count × 4096 bytes` bound. Exceeding the
caller's `max_fact_bytes` blocks the read so PR-03B2B can request a future
chunked-writer decision without changing the existing PR-02 writer.

## Scale boundary

The ledger uses 64 bytes of digest payload per logical row rather than
repeating a roughly 76-byte source-row ID plus an approximately 79-byte source
version. Actual SQLite size, throughput, replay throughput, table cardinality,
and Python `tracemalloc` peak are measured with a direct synthetic benchmark.
`tracemalloc` does not represent all pandas/SQLite native allocations.

Production Excel, the 2.6 million-row master, and the 12 million-row supply
source remain outside this PR. PR-03B2B will own orchestration and PR-02
publication after the sealed month passes its memory bound.
