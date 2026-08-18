# Supply monthly orchestration contract

Status: **Locked implementation contract for PR-03B2B**

Complete contract version: `1.0.0`

This orchestration connects the existing PR-03A supply stream, PR-03B1 exact
three-key lookup, PR-03B2A checkpoint/reducer, and PR-02 Parquet store. It adds
no alternative product join, source adapter, fact schema, or storage format.

## Public API

```python
run_supply_monthly_orchestration(
    *,
    supply_paths: Sequence[Path],
    master_lookup_root: Path,
    master_source_hash: str,
    checkpoint_root: Path,
    output_root: Path,
    max_month_fact_bytes: int,
    batch_size: int = 10_000,
) -> OrchestrationResult
```

The same call handles a new run, complete source replay into an active
checkpoint, publication from a sealed checkpoint, and verification of a
complete run. Callers pass **one closed month's three dekade files**. Adding
later months is a separate run; already published months are left unchanged.
`derive_supply_monthly_run_id(supply_lineage,
master_verification)` exposes the existing PR-03B2A run identity formula; it
does not define a second formula or change checkpoint version `1.0.0`.

`OrchestrationResult` contains:

- `status`: `completed` when this call creates the complete manifest, otherwise
  `unchanged`
- `run_id`
- `written_months`
- `unchanged_months`
- `skipped_unmatched_only_months`
- `relative_complete_manifest_path`

## Execution boundary

The call performs these stages in order:

1. Compute immutable supply workbook lineage and checksums.
2. Verify the immutable master lookup, SQLite checksum, schema, and key count.
3. Derive the checkpoint run ID.
4. Verify an existing sealed checkpoint or recover only its missing sealed
   manifest with the read-only finalizer.
5. For an active/new checkpoint, stream the complete source from the beginning.
6. Open the master lookup once, reset every batch to `RangeIndex`, and join the
   official three-key exactly.
7. Cross-check the join report against a positional boolean mask and apply the
   complete original batch plus mask to the checkpoint.
8. Seal only after normal EOF and valid adapter accounting.
9. Restore at most one sealed month fact at a time under
   `max_month_fact_bytes`.
10. Publish nonempty months through PR-02 and verify every resulting partition.
11. Create the complete manifest only after every publication target verifies.

There is no UDI-only or two-key fallback. A row with the same UDI key but
different item/model keys remains unmatched. A month that exists in the ledger
but has no matched grains is recorded in `skipped_unmatched_only_months` and
does not create an empty Parquet partition. An entirely unmatched run remains
blocked by PR-03B2A.

## Restart behavior

### Active checkpoint

The immutable supply source is replayed from its first row. Existing ledger
rows are no-ops, only a new tail changes accumulator state, and seal remains
forbidden until the current open session proves a complete EOF pass.

### Sealed checkpoint

Excel rows and the master join are not run again. Missing/unverified publication
continues month by month. Existing valid PR-02 partitions are returned as
unchanged. If the sealed SQLite exists but its sealed manifest write previously
failed, only that manifest is recreated by the read-only finalizer.

### Complete run

The sealed checkpoint, all published Parquet files, PR-02 manifests, sizes,
checksums, and row counts are verified again. An identical complete manifest is
a no-op. Any different or damaged artifact is a conflict or integrity error;
the orchestration has no delete, overwrite, force, or automatic repair option.

## Complete manifest

The canonical UTF-8 JSON file is stored at:

```text
<checkpoint_root>/
  supply_monthly_orchestration/
    checkpoint_version=1.0.0/
      run_id=<64hex>/
        _complete_manifest.json
```

It is atomically created only after all target months verify. Its exact fields
are:

- `checkpoint_contract_version`
- `complete_contract_version`
- `complete_payload_fingerprint`
- `fact_schema_version`
- `run_id`
- `sealed_manifest_sha256`
- `storage_contract_version`
- `published_months`, ordered by month, where each entry contains:
  - `month`
  - `fact_fingerprint`
  - `relative_parquet_path`
  - `row_count`
  - `parquet_file_size`
  - `parquet_sha256`
  - `parquet_manifest_sha256`
- `skipped_unmatched_only_months`

`complete_payload_fingerprint` is SHA-256 over the canonical payload excluding
that fingerprint field. The manifest contains no absolute path, execution
time, machine name, or user name. It is kept with the checkpoint; `output_root`
contains only PR-02 Parquet partitions and their monthly manifests. No separate
monthly publication receipt is introduced.

## Path and failure safety

Resolved `checkpoint_root` and `output_root` must be different and neither may
contain the other. This comparison uses `Path.resolve(strict=False)` plus the
platform's normalized path rules.

- Excel, join, batch, EOF, or seal failure prevents all publication.
- PR-02 publication remains atomic per month. A later-month failure preserves
  prior verified months and the immutable sealed checkpoint.
- Partition verification failure prevents the complete manifest.
- Complete-manifest write failure preserves Parquet; rerun verifies publication
  and recreates only the complete manifest.
- Existing incomplete, different, or damaged artifacts are never deleted or
  overwritten automatically.

## Scale boundary

The orchestrator does not materialize the full source or all months. Supply is
bounded by `batch_size`; checkpoint reduction is disk-backed; sealed facts are
restored one month at a time under an explicit byte estimate. The current PR-02
writer still requires one complete month's fact DataFrame. A production month
that exceeds the configured limit remains blocked pending a separate chunked
writer decision.

Synthetic benchmark measurements are diagnostic only. They do not establish
production throughput for 12 million supply rows, the onsite filesystem,
Windows long paths/locks, power interruption, or native-library peak memory.

One direct diagnostic run used 5,000 synthetic rows, six months, and batches of
1,000 rows. It completed in 16.320 seconds (306.4 rows/second): lineage/checksum
0.016 seconds, Excel streaming 8.857 seconds, master lookup open/join 0.446
seconds, checkpoint/reduce 5.787 seconds, seal 0.303 seconds, and monthly fact
restore plus Parquet publication/verification 0.854 seconds. Output size was
0.468 MiB for checkpoint artifacts and 0.047 MiB for Parquet plus manifests.
Python `tracemalloc` peaked at 4.963 MiB; it does not measure all native memory
owned by openpyxl, pandas, NumPy, SQLite, PyArrow, or compression libraries.
