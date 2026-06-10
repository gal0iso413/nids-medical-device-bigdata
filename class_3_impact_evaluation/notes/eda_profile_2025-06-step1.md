# Data Profile — Wesley Partners NIDS Class 3 Impact Evaluation Data Profile Report

> **Agent:** class_3_impact_evaluation  
> **Date:** June 5, 2026  
> **Workbooks profiled:** sample_master_registration_data.xlsx, sample_transaction_supply_data.xlsx

## 1. Executive summary

* **Robust Clinical Coverage Breadth:** In the supply file, transactions supplied directly to hospitals cover exactly **210 unique medical institutions**. This hospital count serves as a direct, high-fidelity measure of Clinical Coverage Breadth on the clinical impact axis of the 2D portfolio matrix.
* **Supplier Monopoly & Vulnerability:** We successfully calculated market concentration indices on the supply transaction logs. The Herfindahl-Hirschman Index (HHI) on supply quantity is **1,428.97** (moderately concentrated). Becton Dickinson Korea holds a **33.76% quantity share** (4,847 units), and the Top 3 suppliers command a joint **50.77% quantity share**, indicating a high vulnerability to supplier disruptions.
* **Substitutability Proxy Feasibility:** In the Master registry, we established a Substitutability Proxy per `품목명` based on the ratio of unique manufacturers to models. For example, `담관용스텐트` has 217 models but only 1 manufacturer, indicating extremely low substitutability (high systemic risk), whereas `수액세트` has 3 models across 3 manufacturers, indicating high substitutability.
* **Supply Classification Null Drift:** The `품목군` (Item Group) column in the Supply sheet has a severe **61.73% null rate** (7,752 null rows), and the populated rows are all labeled as `정형용품II(재료)` despite representing graft stents. This is a critical data quality warning for dynamic portfolio classification.
* **Absolute Sample Disjointness:** The master registration sample and the transaction supply sample are completely disjoint, with **0.00% physical overlap** on keys. This blocks direct linkage of master-specific covariates (such as product lifecycle age derived from `품목허가일자` and detailed `등급` distributions) to the transaction series.
* **Zero-Price Pricing Volume:** 44.7% of all transaction records show a unit price of exactly `0.0`, heavily driven by business-to-business transfers. For price and demand time-series models, these must be filtered by `공급형태` to isolate sales to medical institutions where only 3.7% are zero-price.
* **Halt for PM Approval:** Consistent with the Phase 1 lock, we halt all modeling and graph scripts in `src/` and await PM-aligned files or synthetic lookup parameters to bridge the physical disjointness before proceeding to survival curves or LSTM/SARIMA time-series code.

## 2. Workbook inventory

* **Master Registration File:**
  * Path: `shared_data/sample_master_registration_data.xlsx`
  * Sheet Name: `Sheet1`
  * Rows: 510
  * Columns: 93
* **Transaction Supply File:**
  * Path: `shared_data/sample_transaction_supply_data.xlsx`
  * Sheet Name: `Sheet1`
  * Rows: 12,558
  * Columns: 74

## 3. Column profile

### MCDM Scoring Key Columns Dtypes & Cardinality
* **Master Registration (Clinical Impact & Substitutability):**
  * `등급` (Device Class): `int64`, Null rate: 0.00%, Cardinality: 4 `{Class 1: 231, Class 3: 223, Class 2: 50, Class 4: 6}`
  * `인체이식 의료기기 여부` (Implantable): `str`, Null rate: 0.00%, Cardinality: 2 `{'N': 282, 'Y': 228}`
  * `추적관리대상 의료기기 여부` (Traceability): `str`, Null rate: 0.00%, Cardinality: 2 `{'N': 506, 'Y': 4}`
  * `희소의료기기 여부` (Orphan): `str`, Null rate: 0.00%, Cardinality: 1 `{'아니오': 510}`
  * `수출용 여부` (Export Only): `str`, Null rate: 0.00%, Cardinality: 1 `{'아니오': 510}`
  * `일회용 의료기기 여부` (Single-Use): `str`, Null rate: 0.00%, Cardinality: 2 `{'N': 482, 'Y': 28}`
  * `품목군` (Item Group): `str`, Null rate: 0.00%, Cardinality: 25 (Top: `정형용품II(재료)`: 217 rows, `측정 및 유도용 기구(I)`: 184 rows)
* **Transaction Supply (Supply Risk & Scale):**
  * `등급` (Device Class): `int64`, Null rate: 0.00%, Cardinality: 1 `{Class 4: 12,558}`
  * `인체이식형 의료기기여부` (Implantable): `str`, Null rate: 0.00%, Cardinality: 1 `{'예': 12,558}`
  * `추적관리대상` (Traceability): `str`, Null rate: 0.00%, Cardinality: 1 `{'아니오': 12,558}`
  * `희소의료기기여부` (Orphan): `str`, Null rate: 0.00%, Cardinality: 1 `{'아니오': 12,558}`
  * `수출용여부` (Export Only): `str`, Null rate: 0.00%, Cardinality: 1 `{'아니오': 12,558}`
  * `일회용여부` (Single-Use): `str`, Null rate: 0.00%, Cardinality: 1 `{'아니오': 12,558}`
  * `품목군` (Item Group): `str`, **Null rate: 61.73%**, Cardinality: 1 `{'정형용품II(재료)': 4,806}`
  * `공급수량` (Supply Quantity): `int64`, Null rate: 0.00%, mean: 1.14 (std: 0.50)
  * `요양기관기호(의료기관)` (Institution Code): `float64`, **Null rate: 63.94%**, Cardinality: 210 unique medical institutions

## 4. Dictionary alignment

* **Master Registration Alignment:**
  * Duplicate dictionary entry for `업종` (Column D and CN) is resolved in pandas by loading Column CN as `업종.1`. All 93 columns map perfectly to `description_master_registration.md`.
* **Transaction Supply Alignment:**
  * Excel contains 74 columns vs 71 listed in `description_transaction_supply.md`.
  * The **3 undocumented columns** are `공급연도`, `기준`, and `공급월`.
  * Column `공급연도` captures calendar year (`2024` or `2025`).
  * Column `공급월` captures year and month in YYYYMM format (`202401` to `202410`).
  * Column `기준` is a constant string `'기준'` with 0.00% null rate.

## 5. Join feasibility

* **Join-Key Candidates:**
  * Composite Key: `의료기기품목일련번호` + `모델일련번호` + `UDI-DI 일련번호` (maps to `UDIDI일련번호` in Master).
  * Direct Standard Key: `UDI-DI` (maps to `UDIDI` in Master).
* **Join Overlap Statistics:**
  * Overlapping composite keys: **0 rows (0.00% overlap)**
  * Overlapping standard identifiers (`UDI-DI` ↔ `UDIDI` after standardizing type and stripping leading zeros): **0 rows (0.00% overlap)**
* **Join Blockers:**
  * Complete sample population mismatch. The master registry contains no rows for the single device category (`말초혈관용그라프트스텐트` - peripheral vascular graft stents) reported in the supply transactions.
  * A physical join between these two worksheets returns **0 rows**.
  * This blocks the direct linkage of master-specific clinical covariates (like detailed device class and single-use status) to supply transaction rows.

## 6. Drift and quality flags

* **Pandas Auto-Renaming Drift:** Any ingestion pipeline must be prepared to look for `업종.1` instead of `업종` for CN, or explicitly rename it, to prevent column key-error issues.
* **Supply Classification Null Drift:** The `품목군` (Item Group) column in the Supply sheet has a severe **61.73% null rate** (7,752 null rows), and the populated rows are all labeled as `정형용품II(재료)` despite representing graft stents. This is a critical data quality warning for dynamic portfolio classification.
* **Direct Supplier Monopoly Calculations:** The Herfindahl-Hirschman Index (HHI) on supply quantity is **1,428.97** (moderately concentrated), and the Top 3 suppliers command a joint **50.77% quantity share**, representing a critical supply risk indicator.
* **Zero-Price Pricing Volume:** 44.7% of all transaction records show a unit price of exactly `0.0`, heavily driven by business-to-business transfers (`제조ㆍ수입ㆍ판매(임대)에 공급` has 70.1% zero-pricing). For price and demand time-series models, these must be filtered by `공급형태` to isolate sales to medical institutions where only 3.7% are zero-price.

## 7. Recommended next steps

1. **Incorporate Monopoly Metrics into MCDM:** Utilize the calculated HHI (1,428.97) and Top 3 joint market share (50.77%) directly as weighted components in the MCDM Supply Risk (X-Axis) calculation.
2. **Handle Item Group Null Drift:** Address the 61.73% missingness in the Supply file's `품목군` column by dynamically mapping the item group from the Master registry based on standardized UDI-DIs, rather than relying on the Supply-side `품목군` column.
3. **Use Hospital Count for Breadth:** Quantify the Clinical Impact (Y-Axis) breadth of coverage using the count of unique hospital codes (`요양기관기호(의료기관)`) rather than general distributor transaction counts.
4. **Construct Mock Join-Mappings:** Since the sample worksheets are physically disjoint, any unified MCDM or AI Persona Clustering model testing in Phase 1-2 must utilize simulated link mapping parameters (e.g. mapping Taewoong or GS Medical items to Becton Dickinson transactions) or await aligned production datasets.
5. **Halt for PM Approval:** In accordance with the Phase 1 lock, do not write modeling or clustering scripts in `src/` or advance to Phase 2 until the PM reviews this profile and approves the advancement.
