# NIDS master 3-key lookup contract

> Status: PR-03B1 implementation contract
> Logical schema: `nids_master_product_key` 1.0.0
> Storage contract: 1.0.0
> Next step: PR-03B2 orchestration, monthly aggregation, checkpointing, and Parquet publication

## Scope and factual basis

This layer converts NIDS integrated-registration Excel workbooks into an immutable SQLite membership lookup and joins one bounded PR-03A supply batch by the official three-key identity. It does not enrich supply rows, aggregate monthly facts, publish Parquet, or read production data.

The official master identity is `item_serial × model_serial × udi_serial`, with the equivalent three serials on supply rows. The onsite visit observed approximately 2,625,652 master rows across three sheets and a 99.97% three-key join over the inspected supply run. The 107.03% UDI-only join was inflation caused by multiple master rows, so this implementation deliberately has no UDI-only or two-key lookup. The observed 99.97% is calibration evidence, not a hard-coded acceptance threshold. See [official master fields](../../shared_docs/official/description_master_registration.md), [official supply fields](../../shared_docs/official/description_transaction_supply.md), and [onsite calibration](../../shared_docs/structured/onsite_visit1_summary.md).

## Public API

```python
create_master_lineage(workbook_paths) -> MasterSourceLineage
discover_master_sheets(workbook_path, header_scan_limit=12)
stream_master_product_keys(workbook_paths, header_scan_limit=12) -> MasterKeyStream
build_master_product_lookup(workbook_paths, lookup_root, batch_size=10_000)
verify_master_product_lookup(lookup_root, source_hash)
open_master_product_lookup(lookup_root, source_hash) -> MasterProductLookup
join_supply_batch_to_master(batch, lookup) -> MasterJoinBatchResult
```

`lookup_root` is always a caller-supplied `pathlib.Path`; no institution or user path is embedded. `MasterKeyStream` and `MasterProductLookup` are context managers with idempotent `close()`. Workbooks and SQLite connections close after completion, error, or explicit early exit.

## Source lineage and discovery

Master lineage is a separate namespace from supply lineage. Sorted logical filenames, byte sizes, full SHA-256 values, and adapter contract version form canonical UTF-8 JSON; its SHA-256 becomes both `source_hash` and the suffix of `nids-master-v1:<64hex>`. Absolute paths, input order, execution time, usernames, and machine names are excluded.

Every workbook opens with `openpyxl` `read_only=True` and `data_only=True`. Before header or data iteration, `reset_dimensions()` is used so a stale stored size of `A1` (common in NIDS exports) still yields later columns and rows. Each sheet is inspected only within the bounded header window. All matching sheets are processed in sorted name order. Missing, duplicate, or ambiguous official key headers fail explicitly; sheet names are not hard-coded.

The three official integer codes share one public canonical normalizer with the supply adapter: whitespace is trimmed; exact integers, integral `Decimal`, safe integral floats, and strings such as `10.0` become `10`. Boolean, negative, fractional, non-finite, and precision-unsafe floats above `2**53` are invalid. Leading zeroes are removed only for these official integer-code fields, not for general string identifiers.

## Storage and atomic publication

```text
<lookup_root>/
  master_product_lookup/
    schema_version=1.0.0/
      source_hash=<64 lowercase hex>/
        master_keys.sqlite
        _manifest.json
```

The SQLite database contains only:

```sql
CREATE TABLE product_key(
  item_serial TEXT NOT NULL,
  model_serial TEXT NOT NULL,
  udi_serial TEXT NOT NULL,
  PRIMARY KEY(item_serial, model_serial, udi_serial)
) WITHOUT ROWID;
```

No company, business-registration, UDI text, product description, hospital, or supply identifiers are stored. Duplicate master keys produce one row. The bounded report keeps `rows_read`, `valid_key_rows`, `unique_key_count`, `invalid_key_rows`, `duplicate_key_rows`, up to 20 invalid locations, and an omitted count.

The database and canonical manifest are written to a private same-volume directory and atomically moved to the final source-hash directory. A complete identical source is an unchanged no-op. A missing, malformed, checksum-mismatched, wrong-path, wrong-schema, or wrong-count artifact fails closed. A competing identical publisher is unchanged; different content is a conflict. There is no `force`, overwrite, delete, or automatic repair path, and a distinct source snapshot remains in a distinct directory.

Manifest example (hashes abbreviated only in this document):

```json
{"adapter_contract_version":"1.0.0","database_file_size":12288,"database_sha256":"<64hex>","dataset_name":"master_product_lookup","duplicate_key_rows":2,"invalid_key_locations":["synthetic.xlsx:data:row=7"],"invalid_key_omitted":0,"invalid_key_rows":1,"logical_schema_name":"nids_master_product_key","logical_schema_version":"1.0.0","relative_database_path":"master_product_lookup/schema_version=1.0.0/source_hash=<64hex>/master_keys.sqlite","rows_read":103,"source_hash":"<64hex>","source_version":"nids-master-v1:<64hex>","source_workbooks":[{"byte_size":1234,"logical_name":"synthetic.xlsx","sha256":"<64hex>"}],"storage_contract_version":"1.0.0","unique_key_count":100,"valid_key_rows":102}
```

The real manifest uses full hashes and contains no absolute path, host detail, execution timestamp, or source-row sample.

## Supply batch join

The input columns must exactly equal PR-03A `SOURCE_BATCH_COLUMNS`, and exactly one supply `source_version` must be present. All three key components and `source_row_id` are required. A bounded temporary SQLite table receives normalized batch keys with their positions, then one bound set join selects matching positions. The published main database is opened read-only. There is no row-by-row `SELECT` and no unbounded `IN` clause.

The output `matched_rows` retains every input column, original row order, and duplicate supply rows. Its report contains `rows_input`, `rows_matched`, `rows_unmatched`, exact decimal match rate, up to 20 unmatched `source_row_id` values plus omitted count, and both master and supply source versions. Unmatched full rows and master values are not emitted. `rows_matched` cannot exceed `rows_input`.

## Deferred decisions and PR-03B2 boundary

- Production lookup root, Windows long-path policy, encryption, access control, retention, backup, and recovery.
- Actual 2.6-million-row build time, Excel shared-string/XML cost, SQLite filesystem behavior, and process peak memory.
- Join acceptance/warning policy. The onsite 99.97% observation is not a threshold.
- PR-03B2 will orchestrate supply batches, exact membership joins, PR-01 normalization/aggregation, checkpoints, and PR-02 publication. It must preserve master and supply lineage and must not introduce UDI-only fallback.
