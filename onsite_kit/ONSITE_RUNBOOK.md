# NIDS Class 1 — Onsite Visit Kit (minimal)

Bring this zip + laptop. Use **real** master/supply files onsite — not lab samples.
**No conda required** — PowerShell + Python `venv` only.

## Reality check (Visit 1 / production)

| Dataset | Onsite shape |
|---------|----------------|
| Master | **1 workbook**, often **multiple sheets** (merged) |
| Supply | **Many workbooks** (Visit 1: **12 files**), sheets may split ~1M rows; header auto-detected |

## 0) One-time setup (PowerShell, no conda)

```powershell
# 1) Go to kit root (folder that contains class_1_anomaly_detection\)
cd C:\경로\키트루트

# 2) Pick a Python 3.10–3.12 if available (3.11 preferred for torch). Else plain python.
py -3.11 --version
# if that fails, try:
# py -3.12 --version
# python --version

# 3) Create and activate a local virtual environment
py -3.11 -m venv .venv
# fallback:  python -m venv .venv

.\.venv\Scripts\Activate.ps1
# If blocked:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 4) Upgrade pip and install base deps
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 5) Optional GNN (only if time / network allows)
# python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
# python -m pip install -r class_1_anomaly_detection\requirements-ml.txt
```

Every **new** PowerShell window:

```powershell
cd C:\경로\키트루트
.\.venv\Scripts\Activate.ps1
```

Prompt should show `(.venv)`.

## Env vars (same window as the run)

```powershell
$env:NIDS_MASTER_XLSX = "D:\nids_data\master\통합정보등록.xlsx"
$env:NIDS_SUPPLY_DIR  = "D:\nids_data\supply_recent"   # folder of many xlsx
```

Lab / single-file only:

```powershell
$env:NIDS_SUPPLY_XLSX = "D:\path\to\one_supply.xlsx"
# leave NIDS_SUPPLY_DIR unset
```

Do **not** set `NIDS_SUPPLY_XLSX` to a folder.

## First-visit run

Prefer a `supply_recent` folder with **only ~last 4 months** of supply workbooks.

```powershell
cd C:\경로\키트루트
.\.venv\Scripts\Activate.ps1

$env:NIDS_MASTER_XLSX = "D:\path\to\master.xlsx"
$env:NIDS_SUPPLY_DIR  = "D:\path\to\supply_folder_recent_only"

python -m class_1_anomaly_detection.src.ingest.materialize_parquet --force --last-n-months 4

python -c "import json; print(json.load(open('class_1_anomaly_detection/data/parquet/manifest.json',encoding='utf-8'))['months'])"

$ANCHOR = "202604"   # replace with last month from the print above
python -m class_1_anomaly_detection.src.eda.run_graph_eda --anchor-month $ANCHOR
python -m class_1_anomaly_detection.src.experiments.export_pyg_graph --anchor-month $ANCHOR
python -m class_1_anomaly_detection.src.experiments.run_gadnr_production --anchor-month $ANCHOR
python -m class_1_anomaly_detection.src.experiments.build_ui_artifacts --anchor-month $ANCHOR
python -m streamlit run class_1_anomaly_detection\app.py
```

If torch was not installed, stop after `run_graph_eda` and keep CSV outputs.

## Sleep note

Screen off is usually OK. System sleep stops jobs. If power settings are locked, keep a second PowerShell running the SetThreadExecutionState loop (see prior Korean guide) while this window runs Python.

## Later visit

```powershell
python -m class_1_anomaly_detection.src.ingest.materialize_parquet --force
python -m class_1_anomaly_detection.src.eda.run_graph_eda --all-anchors
```

## Bring home (if approved)

- `class_1_anomaly_detection\data\parquet\`
- `class_1_anomaly_detection\output\`
