# Data Profile — Wesley Partners NIDS Sample Data Profile Report

> **Agent:** class_1_anomaly_detection  
> **Date:** June 5, 2026  
> **Workbooks profiled:** sample_master_registration_data.xlsx, sample_transaction_supply_data.xlsx

## 1. Executive summary

* **Absolute Data Disjointness:** The master registration sample (`sample_master_registration_data.xlsx`) and the transaction supply sample (`sample_transaction_supply_data.xlsx`) represent completely disjoint sets of medical devices. There is **0.00% physical overlap** across standard join keys (item serial numbers, model names, UDI-DIs, and license numbers).
* **Master Sheet Characteristics:** The master registration sheet consists of 510 rows and 93 columns representing 36 unique manufacturers and 44 unique medical items (dominated by biliary stents from Taewoong Medical and orthopedic devices from GS Medical).
* **Supply Sheet Characteristics:** The transaction supply sheet contains 12,558 rows and 74 columns representing 115 suppliers and 355 receivers. It is entirely dominated by exactly **one** device category: *peripheral vascular graft stents* (말초혈관용그라프트스텐트), which does not exist in the master file.
* **Column Discrepancies & Drift:** The transaction supply Excel contains 3 undocumented columns (`공급연도`, `기준`, `공급월`) not present in the official data dictionary. The master registration Excel contains a duplicate column name `업종` (Column D and CN) which pandas automatically loads as `업종.1`.
* **High Missingness Guardrails:** 45 out of 93 columns in the master file have null rates exceeding 50% (such as software `버전` and `제조원국가` at 100%). In the supply file, 10 out of 74 columns exceed 50% nullness, including critical tracking variables `제조연월` and `일련번호` which are 100% null.
* **Zero-Price Transaction Volume:** A high portion (44.7% of total, 54.7% of non-null) of supply records have exactly `0.0` as their unit price (`공급단가`). Cross-tabulation reveals this is heavily concentrated in business-to-business transactions (where 70.1% are zero-price), whereas sales to medical institutions have zero-price in only 3.7% of cases.
* **Join Blocked for EDA:** Physical join operations on standard composite keys (`의료기기품목일련번호` + `모델일련번호` + `UDIDI일련번호` ↔ `UDI-DI 일련번호`) result in exactly 0 matching rows. Downstream pipeline testing must use simulated mock alignments until aligned files are loaded.

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

### Key Identity Columns Dtypes & Cardinality
* **Master Registration Keys:**
  * `의료기기품목일련번호` (No. 63): `int64`, Null rate: 0.00%, Cardinality: 510 (100% unique)
  * `모델일련번호` (No. 64): `int64`, Null rate: 0.00%, Cardinality: 510 (100% unique)
  * `UDIDI일련번호` (No. 65): `int64`, Null rate: 0.00%, Cardinality: 510 (100% unique)
  * `UDIDI` (No. 16): `str` (or object), Null rate: 0.00%, Cardinality: 503
  * `품목허가번호` (No. 10): `str`, Null rate: 0.00%, Cardinality: 44
  * `모델명` (No. 12): `str`, Null rate: 0.00%, Cardinality: 509
* **Transaction Supply Keys:**
  * `의료기기품목일련번호` (No. 20): `int64`, Null rate: 0.00%, Cardinality: 2
  * `모델일련번호` (No. 61): `int64`, Null rate: 0.00%, Cardinality: 38
  * `UDI-DI 일련번호` (No. 28): `int64`, Null rate: 0.00%, Cardinality: 38
  * `UDI-DI` (No. 27): `int64`, Null rate: 0.00%, Cardinality: 38
  * `품목허가번호` (No. 25): `str`, Null rate: 0.00%, Cardinality: 1
  * `모델명` (No. 26): `str`, Null rate: 0.00%, Cardinality: 38

### Guardrails: Columns Exceeding 50% Null Rate (High Missingness)
* **Master Registration (45 Columns):**
  * `버전`, `관리자 이메일`, `관리자 전화번호`, `사용종료 사유`: 100.00% Null
  * `물류바코드3/4/5` and associated packaging quantities/sequences: 100.00% Null
  * `제조원국가`: 100.00% Null
  * `통합정보 사용중단 일자(YYYYMMDD)`: 100.00% Null
  * `멸균방법2/3` and their other options: 100.00% Null
  * `물류바코드2` and associated packaging quantities/sequences: 99.80% Null
  * `유효기간 만료여부`, `유통취급조건`, `경고금기내용`, `품목허가번호 취소/취하 일자`: 99.80% Null
  * `요양급여코드1`: 96.27% Null
  * `저장조건`: 61.37% Null
  * `멸균방법1`: 57.65% Null
  * `프탈레이트류 포함 여부`: 50.20% Null
* **Transaction Supply (10 Columns):**
  * `제조연월` (UDI-PI): 100.00% Null
  * `일련번호` (UDI-PI): 100.00% Null
  * `포장내수량 중 낱개 회수수량`: 100.00% Null
  * `품목취소취하여부`: 100.00% Null
  * `납품업체일련번호`: 98.42% Null
  * `업허가번호`: 72.89% Null
  * `최초접수일자`: 69.52% Null
  * `비고` (Remarks): 64.19% Null
  * `요양기관기호(의료기관)`: 63.94% Null
  * `품목군`: 61.73% Null

### Guardrails: Columns with 20–50% Null Rate (Quality Indicators)
* **Master Registration (2 Columns):**
  * `제품일련번호 사용여부`: 49.02% Null
  * `사용기한 사용여부`: 48.63% Null
* **Transaction Supply (1 Column):**
  * `업허가번호(의료기기판매,임대업)`: 27.11% Null

## 4. Dictionary alignment

* **Master Registration Alignment:**
  * Column name `업종` occurs twice in the official dictionary (No. 4, Column D and No. 92, Column CN). Pandas automatically loads Column CN as `업종.1`.
  * All 93 columns in the Excel file map perfectly to No. 1–93 in `description_master_registration.md`.
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
  * License/Product Key: `품목허가번호` + `모델명`.
* **Join Overlap Statistics:**
  * Total Master Rows: 510 (100% unique on Composite Key)
  * Total Supply Rows: 12,558 (100% unique on Composite Key `거래처 코드` + `공급내역기준연월` + `공급내역작업일련번호` + `공급내역일련번호`)
  * Unique Master `UDIDI` values: 503
  * Unique Supply `UDI-DI` values: 38
  * Overlapping composite keys: **0 rows (0.00% overlap)**
  * Overlapping standard identifiers (`UDI-DI` ↔ `UDIDI` after coercing types and stripping leading zeros): **0 rows (0.00% overlap)**
* **Join Blockers:**
  * Complete sample population mismatch. The master registry contains no rows for the single device category (`말초혈관용그라프트스텐트` - peripheral vascular graft stents) reported in the supply transactions.
  * A standard physical inner join between these two specific worksheets will return **0 rows**.

## 6. Drift and quality flags

* **Pandas Auto-Renaming Drift:** Any ingestion pipeline must be prepared to look for `업종.1` instead of `업종` for CN, or explicitly rename it, to prevent column key-error issues.
* **Int-to-String Type Coercion:** Master standard codes (`UDIDI`) contain leading zeros (e.g. `08800313887990`) and are stored as strings. Supply standard codes (`UDI-DI`) are read as integers (e.g. `801741105593`). Joined adapters must force string-type casting and handle leading zeros.
* **Zero-Price Pricing Anomalies:** 5,614 supply transactions (44.7% of total) have `공급단가 = 0.0`. This is heavily driven by business-to-business transfers (`제조ㆍ수입ㆍ판매(임대)에 공급` has 70.1% zero-pricing). For price-outlier tracking, calculations must be filtered by `공급형태` to isolate sales to medical institutions (`의료기관에 공급` has only 3.7% zero-pricing).
* **Missing UDI-PI Trackers:** Supply rows contain 100.00% null values for `제조연월` and `일련번호`, meaning precise serial/batch-level expiration or manufacture-date anomaly detection is impossible with the current sample tier.

## 7. Recommended next steps

1. **Implement Class-Specific Data Adapter:** Write an ingestion adapter inside `class_1_anomaly_detection/` that loads the workbooks, casts key columns to consistent types, strips leading zeros, and handles the `업종.1` duplicate naming logic.
2. **Design Mock Aligned Datasets for Testing:** Since the real worksheets are physically disjoint in the sample tier, any graph database construction or joint EDA testing must construct mock/synthetic linkages (e.g., mappingTaewoong or GS Medical items to Becton Dickinson transactions) or request aligned datasets from the PM.
3. **Price Outlier Filter:** Restrict price-distribution anomaly detection models to transactions where `공급형태` is `의료기관에 공급` to avoid skewing metrics with zero-price B2B or sample transfers.
4. **Halt for PM Approval:** In accordance with the Phase 1 lock, do not write modeling or graph-building scripts in `src/` or advance to Phase 2 until the PM reviews this profile and approves the advancement.
