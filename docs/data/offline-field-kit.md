# Offline Windows field kit

Status: **PR-04B offline environment contract**

This kit reproduces the PR-04A data-pipeline runtime on an internet-connected
preparation PC and installs it into a project-only virtual environment on an
approved offline Windows x64 PC. It does not install Python automatically,
change global `site-packages`, process production data, or add another pipeline
implementation. Institutional media approval and software-import procedures
remain mandatory.

## Locked runtime

The recommended interpreter is the official **CPython 3.13.12 Windows x64**
installer. The repository's 179-test baseline passed on Python 3.13.12 64-bit
with pandas 3.0.3, PyArrow 24.0.0, openpyxl 3.1.5, and NumPy 2.4.6. The direct
data-pipeline requirements are pandas, PyArrow, and openpyxl; NumPy is also a
direct runtime import. The lock additionally includes the exact transitive
runtime dependencies et-xmlfile, python-dateutil, six, and tzdata.

The compiled packages publish CPython 3.13 Windows x64 wheels; the remaining
packages publish platform-independent wheels. The lock at
`tools/offline/requirements-field-kit-win-py313.lock` pins all eight versions
and the SHA-256 of the selected wheel. Source distributions are not permitted.
The builder also requires the official CPython 3.13.12 x64 installer SHA-256
and a valid Python Software Foundation Authenticode signature.

## Online preparation

Use a clean clone at the approved commit. Obtain the official 64-bit Windows
installer from python.org and verify its publisher through the institutional
software intake process. Do not run it as part of kit creation. Choose an
output directory outside the Git repository; the builder refuses existing
targets and dirty working trees.

```powershell
powershell -ExecutionPolicy Bypass -File tools/offline/build-field-kit.ps1 `
  -PythonExe "C:\Program Files\Python313\python.exe" `
  -PythonInstaller "D:\Approved Software\python-3.13.12-amd64.exe" `
  -OutputDirectory "D:\Field Kits\nids-field-kit"
```

The online Python must itself be CPython 3.13.12 x64. The builder downloads
only the eight locked wheels for `cp313`/`win_amd64`, creates a tracked-source
snapshot from an allowlist, and writes `field-kit-manifest.json`. It rejects
sdists and excludes `.git`, untracked files, environment files, actual data,
Excel, Parquet, SQLite/checkpoints, wheels or nested ZIPs, `node_modules`,
`dist`, credentials, and local internal paths from the source snapshot.

The source snapshot contains `data_pipeline`, synthetic tests, the example
configuration, data-pipeline requirements, and field documentation at the
recorded commit. The manifest contains only relative paths, roles, sizes,
SHA-256 values, the source commit, and locked runtime metadata. It contains no
user name, host name, build time, source path, installer path, or output path.

Copy the resulting directory as-is to an institutionally approved medium.
Do not add files to the kit directory after creation: exact-set verification
treats both missing and additional files as tampering.

## Offline verification and installation

Install the supplied official Python manually according to the approved
institutional procedure. The kit never starts the installer and never requests
administrator privileges. Then run:

```powershell
Set-Location "E:\승인 반입\nids-field-kit"
powershell -ExecutionPolicy Bypass -File .\verify-field-kit.ps1
powershell -ExecutionPolicy Bypass -File .\install-field-env.ps1 `
  -PythonExe "C:\Program Files\Python313\python.exe"
powershell -ExecutionPolicy Bypass -File .\smoke-test.ps1
```

By default the clean environment is created as `nids-field-runtime` beside,
not inside, the kit. A different `-InstallDirectory` may be supplied and may
contain Korean characters and spaces, but it must not already exist. The
installer creates a staging directory, makes a venv, and invokes pip with
`--no-index --find-links`, `--only-binary=:all:`, `--require-hashes`, and
`--no-deps`. It never uses global or user site-packages. On failure it removes
only its new staging directory and never replaces an existing environment.

The smoke test verifies required imports, CLI help, example TOML parsing, and
the 17 synthetic PR-04A CLI tests. It reads no production Excel and reports
`network_access: not_attempted`; pip index access is explicitly disabled.

## Field execution and resume

Copy `config/field-run.example.toml` from the installed source to an untracked
local `field-run.toml`. Never edit or store internal paths inside the kit or
repository snapshot. From the installed source with the venv Python (replace
the example locations with approved local paths):

```powershell
$runtime = "E:\승인 반입\nids-field-runtime"
Set-Location (Join-Path $runtime "source")
& (Join-Path $runtime ".venv\Scripts\python.exe") -m data_pipeline.cli preflight --config field-run.toml
& (Join-Path $runtime ".venv\Scripts\python.exe") -m data_pipeline.cli run --config field-run.toml
& (Join-Path $runtime ".venv\Scripts\python.exe") -m data_pipeline.cli status --config field-run.toml
& (Join-Path $runtime ".venv\Scripts\python.exe") -m data_pipeline.cli verify --config field-run.toml
```

After Ctrl+C, power interruption, or a reported processing error, preserve the
immutable input, config, lookup, checkpoint, and output roots. Rerun preflight
and then `run` with the same config. Do not delete WAL/checkpoint files or edit
manifests. The field runner delegates recovery to the existing checkpoint and
publication contracts.

## Failure handling

- Manifest checksum, missing-file, or additional-file failure: stop and obtain
  a newly approved kit; do not replace individual files.
- Installer signature or Python architecture/version mismatch: stop and use
  the approved CPython 3.13.12 Windows x64 installer.
- Insufficient storage: retain existing artifacts, obtain an approved larger
  location, and rerun only after reviewing checkpoint/output path policy.
- Permission failure: grant the operator read access to inputs and write access
  only to approved artifact roots; do not run the kit as administrator merely
  to bypass the error.
- Windows long-path warning: use approved shorter roots or the institution's
  long-path policy; do not rename contracted partition/checkpoint directories.
- WAL/checkpoint recovery error: preserve the database and sidecars for
  investigation. Never delete, reset, or auto-repair them.

## Onsite benchmark record

Record this outside Git and exclude internal paths and identifiers:

```text
Date / approved device identifier:
Windows / storage medium / free bytes:
Python / pandas / pyarrow / openpyxl / numpy:
Kit source commit / manifest verification result:
Supply workbook count and bytes / Master mode:
Batch size / month fact memory ceiling:
Clean run duration / resume duration and point:
Rows per second / checkpoint bytes / Parquet bytes:
Largest month rows / grains / estimated DataFrame bytes:
Peak memory (measurement tool and coverage):
Power-loss or interruption method / WAL recovery result:
Warnings and blocked conditions:
```

Never remove from the institution or commit source workbooks, Master or Supply
rows, Excel/Parquet/SQLite/checkpoint artifacts, manifests tied to internal
lineage, credentials, logs containing internal paths, screenshots, or benchmark
records that reveal identifiers.

Remaining onsite decisions include approved media handling, installer approval,
storage/encryption/access controls, Windows long-path policy, backup/retention,
power-loss procedures, 12-million-row runtime, filesystem throughput, peak
native memory, and incident recovery ownership.
