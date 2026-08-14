# Windows field runner

Status: **PR-04A offline execution contract**

For reproducible installation on an internet-blocked Windows PC, first create
and verify the approved wheel/source bundle described in
[Offline Windows field kit](offline-field-kit.md).

The field runner is a standard-library `argparse` and `tomllib` wrapper around
the already locked data-pipeline APIs. It does not define another Excel reader,
join, reducer, checkpoint, Parquet writer, or artifact schema. It does not use
the network, download packages, expose HTTP, or connect Class 1/2/3 services.

## Requirements and configuration

- Python 3.11 or later
- versions allowed by `requirements-data-pipeline.txt`
- an offline-installed `pandas`, `pyarrow`, and `openpyxl` environment
- immutable Supply workbooks and either immutable Master workbooks or an
  already published Master lookup

PR-04A was locally validated with Python 3.13.12, pandas 3.0.3,
PyArrow 24.0.0, and openpyxl 3.1.5. These are validation facts, not permission
to widen the bounded dependency ranges.

Copy `config/field-run.example.toml` to an untracked `field-run.toml` and edit
it locally. Relative paths are resolved relative to that config file. The
config contract is strict: unknown fields, duplicate input paths, nonpositive
batch/memory values, and specifying both or neither Master source modes fail.

```toml
config_version = "1.0.0"

[paths]
supply_workbooks = ["./inputs/supply/example-supply.xlsx"]
checkpoint_root = "./field-artifacts/checkpoints"
output_root = "./field-artifacts/monthly-facts"

[master]
lookup_root = "./field-artifacts/master-lookup"
source_hash = "<64 lowercase hex from the published lookup>"

[run]
batch_size = 10000
max_month_fact_bytes = 536870912
minimum_free_bytes = 0
```

For Master-workbook mode, remove `source_hash` and set
`workbooks = ["./inputs/master/example-master.xlsx"]`. `run` then calls the
existing immutable Master lookup builder and reuses an identical published
lookup. It does not implement a second Master adapter.

`minimum_free_bytes = 0` is an explicit unconfigured state: preflight reports
available bytes with a warning. Set an onsite-approved floor before production;
this document does not invent storage capacity policy.

Never commit the working config, internal paths, real filenames, hashes tied to
internal snapshots, credentials, or copied command output containing local
details. `field-run.toml` and `field-run.local.toml` are ignored; differently
named local configs remain the operator's responsibility.

## First run

From the repository root in the approved offline Python environment:

```powershell
python -m data_pipeline.cli preflight --config field-run.toml
python -m data_pipeline.cli run --config field-run.toml
python -m data_pipeline.cli status --config field-run.toml
python -m data_pipeline.cli verify --config field-run.toml
```

Preflight is deliberately light. It reads at most one byte from each input,
does not traverse Excel rows, and does not compute full workbook or database
checksums. It checks:

- Python and dependency versions
- input existence and read access
- output/checkpoint write-delete probes on their nearest existing parents
- non-overlapping checkpoint/output roots
- free space against the operator-supplied floor
- projected Windows path length and `LongPathsEnabled`
- a bounded inventory of active, sealed, complete, and incomplete checkpoints
- presence (not checksum) of a configured published Master lookup

A preflight pass is not an integrity verification. `run`, `status`, and
`verify` compute immutable lineage or perform the applicable full verification.

## Interruption and resume

Do not delete, rename, reset, or edit checkpoint artifacts. After an ordinary
process interruption or a reported stage error, keep the workbooks, lookup,
config, and roots unchanged and run:

```powershell
python -m data_pipeline.cli preflight --config field-run.toml
python -m data_pipeline.cli run --config field-run.toml
```

The existing orchestration contract replays the immutable source into an active
checkpoint, continues publication from a sealed checkpoint, verifies existing
identical monthly partitions as unchanged, and recreates only a missing
complete manifest after all underlying artifacts verify. The CLI neither
changes that idempotency contract nor offers force, delete, reset, or repair.

## Status and verification

`status` computes exact Supply and Master lineage to identify the run. It then
reports one of `not_started`, `active`, `sealed_unpublished_or_incomplete`,
`complete_unverified`, `incomplete_artifact`, or `master_lookup_missing`.
Status does not claim artifact integrity; its JSON has `verified: false`.

`verify` requires both the complete and sealed manifests. It calls the existing
sealed-checkpoint verifier and then the existing complete-state orchestration
path. A valid completed run returns `status: verified`; each Parquet partition,
manifest, size, checksum, row count, and cross-stage fingerprint is checked by
the already locked contracts. Missing or damaged artifacts fail closed and are
not automatically repaired.

Exit codes are stable for field scripts:

- `0`: command succeeded (preflight warnings are allowed)
- `2`: `argparse` command-line usage error
- `3`: TOML/config contract error
- `4`: preflight failed
- `5`: status or run failed
- `6`: verify failed
- `130`: interrupted by the operator; rerun the same config

CLI output is bounded JSON. Error output names the stage, error type, and a
recovery direction. Known configured absolute paths are replaced with logical
path labels in propagated exception messages. Artifact manifests remain owned
by the existing contracts and contain no absolute paths, user, host, or run
timestamp.

## Representative errors

- `checkpoint_output_disjoint: fail`: choose separate, non-nested roots; do not
  move existing artifacts into one another.
- `published_master_lookup: fail`: build or copy the immutable lookup and use
  its exact source hash.
- package/version failure: install the approved wheel bundle offline; the CLI
  never downloads packages.
- Windows path warning: use approved shorter roots or enable the institutional
  long-path policy. Do not manually rename contracted artifact directories.
- incomplete checkpoint inventory: inspect logs and artifacts manually, then
  rerun the unchanged source/config. The CLI never deletes it.
- `CheckpointMemoryLimitError`: retain the active checkpoint and obtain an
  approved larger `max_month_fact_bytes`, or stop for a chunked-writer decision.
- checksum, manifest, lineage, or conflict error: quarantine the run for
  investigation. Do not edit manifests, overwrite partitions, or reset the
  checkpoint.

## Onsite benchmark record

Record measurements outside the repository or in an approved non-sensitive
report. Do not paste internal paths or source identifiers into Git history.

```text
Date / device class:
Python / pandas / pyarrow / openpyxl:
Windows version / LongPathsEnabled:
Storage medium and free bytes (no path):
Supply workbook count / total bytes / emitted rows:
Master source mode / unique keys:
Batch size / max month fact bytes:
New run wall time:
Resume point and resumed wall time:
Rows per second:
Checkpoint bytes:
Parquet + manifest bytes:
Largest month matched rows / grains / estimated fact bytes:
Peak process memory (tool and coverage stated):
Power/interruption method and observed recovery:
Warnings / blocked conditions:
```

The current synthetic benchmark is not a production SLA. Actual Windows
filesystem throughput, shared-string/XML cost, native memory, 12-million-row
runtime, power-loss behavior, path policy, storage capacity, encryption,
permissions, retention, backup, and recovery remain onsite decisions.
