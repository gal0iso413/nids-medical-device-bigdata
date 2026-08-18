# Data Profile — Wesley Partners NIDS Top7 Data Profile Report

> **Agent:** class_1_anomaly_detection  
> **Date:** June 10, 2026  
> **Workbooks profiled:** top7_master_registration_data.xlsx, top7_transaction_supply_data.xlsx

## 1. Executive summary

* **Successful High-Volume Ingestion:** Successfully loaded and profiled both top7 datasets in WSL using the high-performance `python-calamine` Rust engine. The Master Registration workbook contains **221 rows** (93 columns) and the Transaction Supply workbook contains **704,315 rows** (71 columns). Sheet 2 was discovered to be named `공급내역 보고자료` in the workbook (matching the role of `공급내역 실제자료` in the data layer specs).
* **Flawless 3-Key Join Feasibility:** Unlike the sample tier (which has 0% join overlap), the top7 modeling tier is mathematically **100.00% joinable**. Joining the datasets on the composite key `['의료기기품목일련번호', '모델일련번호', 'UDI-DI 일련번호']` matching to Master `['의료기기품목일련번호', '모델일련번호', 'UDIDI일련번호']` results in exactly **704,315 joined rows** (100.00% match).
* **Strict Join Key Constraints:** Joining on `UDI-DI` alone introduces a **+4.86% row-count inflation** (738,567 rows) because identical UDI-DIs are registered across different licenses. Joining on `[의료기기품목일련번호, 모델일련번호]` alone results in a massive **+162.59% inflation** (1,849,433 rows) due to multiple packaging quantities. Thus, the 3-key composite is **strictly mandatory** for modeling integrity.
* **Master Expiry Gaps & Supply-Level Bypass:** In the Master registry, license-linked expiration fields (`유효기간`) are **100.00% null**. However, in the Supply transaction records, `사용기한` (Expiration Date) is **92.97% populated**, offering an excellent proxy for analyzing device lifespan, shelf life, and expiration-date anomalies.
* **Pricing Segmentation Strategy:** While `공급단가` (Supply Unit Price) has a global null rate of 21.51%, segmenting by `공급형태` = `의료기관에 공급` (the primary hospital-destination transaction type with 373,480 rows) reveals that only **7.19%** of unit prices are null and only **1.96%** are zero. This leaves **90.85%** of hospital transactions with valid commercial prices, making this segment the prime target for anomaly detection models and discarding unpriced B2B distribution transfers.
* **Discard Recipient Verification:** There are 1,110 discard records (`공급구분` = `폐기`). Receiver details in these records are **100.00% null** across `공급받은자`, `공급받은자 사업자등록번호`, and `요양기관기호(의료기관)`, validating regulatory business rules perfectly.

## 2. Workbook inventory

* **Master Registration Workbook:**
  * **Path:** `shared_data/top7_master_registration_data.xlsx`
  * **Tab Name:** `Sheet1`
  * **Dimensions:** 221 rows, 93 columns
* **Transaction Supply Workbook:**
  * **Path:** `shared_data/top7_transaction_supply_data.xlsx`
  * **Tab Names:** `['개요', '공급내역 보고자료']`
  * **Tab Profiled:** `공급내역 보고자료` (Sheet 2, actual transaction data)
  * **Dimensions:** 704,315 rows, 71 columns

## 3. Column profile

### Key Column Statistical Profiles

| Table | Column Name | Pandas Dtype | Null Count | Null Rate | Cardinality | Purpose / Description |
|---|---|---|---|---|---|---|
| **Master** | `의료기기품목일련번호` | `int64` | 0 | 0.00% | 7 | Item License Serial Number (BK) |
| **Master** | `모델일련번호` | `int64` | 0 | 0.00% | 110 | Model Serial Number (BL) |
| **Master** | `UDIDI일련번호` | `int64` | 0 | 0.00% | 221 | UDI-DI Serial Number (BM) |
| **Master** | `UDIDI` | `int64` | 0 | 0.00% | 213 | Unique Device Identifier code (P) |
| **Master** | `품목허가번호` | `object` (str) | 0 | 0.00% | 7 | Item License Number (J) |
| **Master** | `모델명` | `object` (str) | 0 | 0.00% | 110 | Model Name (L) |
| **Master** | `업종` | `object` (str) | 0 | 0.00% | 2 | Business type (D) - Manufacturing/Importing |
| **Master** | `업종.1` | `object` (str) | 0 | 0.00% | 2 | Detailed business type (CN) |
| **Supply** | `의료기기품목일련번호` | `int64` | 0 | 0.00% | 7 | Item License Serial Number (T) |
| **Supply** | `모델일련번호` | `int64` | 0 | 0.00% | 57 | Model Serial Number (BI) |
| **Supply** | `UDI-DI 일련번호` | `int64` | 0 | 0.00% | 100 | UDI-DI Serial Number (AB) |
| **Supply** | `UDI-DI` | `int64` | 0 | 0.00% | 94 | Unique Device Identifier code (AA) |
| **Supply** | `품목허가번호` | `object` (str) | 0 | 0.00% | 7 | Item License Number (Y) |
| **Supply** | `모델명` | `object` (str) | 0 | 0.00% | 57 | Model Name (Z) |
| **Supply** | `업종` | `object` (str) | 0 | 0.00% | 3 | Supplier's business type (D) |
| **Supply** | `공급구분` | `object` (str) | 0 | 0.00% | 5 | Transaction classification (F) |
| **Supply** | `공급형태` | `object` (str) | 21,420 | 3.04% | 4 | Supply destination type (G) |
| **Supply** | `공급단가` | `float64` | 151,504 | 21.51% | 3,921 | Unit price (AK) |
| **Supply** | `공급금액` | `float64` | 120,871 | 17.16% | 17,226 | Total transaction amount (AL) |

### Quality Flagged Columns (Missingness Thresholds)

#### Master Registration Missingness
* **Extreme Nulls (>50%):**
  * `제조원국가` (100.00% null) - Crucial manufacturer country info is entirely missing.
  * `버전` (100.00% null) - Standalone software version details.
  * `경고금기내용` (100.00% null) - Warning/contraindication texts.
  * `요양급여코드 미입력 사유` (100.00% null) - Reasoning for missing benefit codes.
  * `멸균방법1`~`3` and related columns (100.00% null) - Disinfectant specs.
  * `유효기간 만료여부`, `취소/취하`, `품목허가번호 취소/취하 일자` (100.00% null) - License-status details.
  * `물류바코드5` (100.00% null)
  * `물류바코드4` and related qty/step (98.64% null)
  * `요양급여코드2`~`4` (97.74% null)
  * `코드중복등록사유` (97.29% null)
  * `제품 추가설명` (96.38% null)
  * `물류바코드3` and related qty/step (87.78% null)
  * `물류바코드2` and related qty/step (85.97% null)
  * `사용종료 사유` and `통합정보 사용중단 일자(YYYYMMDD)` (80.54% null)
  * `저장조건` and `유통취급조건` (76.92% null)
  * `고객센터연락처` (65.61% null)
  * `고객센터명` (61.54% null)
  * `브랜드명` (54.30% null)
* **Moderate Nulls (20% to 50%):**
  * `요양급여코드1` (32.13% null)
  * `요양급여코드(','로 구분)` (32.13% null)
  * `갱신신청 상태` (22.62% null)

#### Transaction Supply Missingness
* **Extreme Nulls (>50%):**
  * `품목취소취하여부` (100.00% null)
  * `납품업체일련번호` (97.30% null)
  * `포장내수량 중 낱개 회수수량` (94.46% null)
  * `업허가번호` (92.97% null)
  * `일련번호` (92.06% null)
  * `제조연월` (90.52% null)
  * `비고` (85.83% null)
* **Moderate Nulls (20% to 50%):**
  * `제품명` (49.11% null)
  * `요양기관기호(의료기관)` (47.85% null)
  * `공급단가` (21.51% null)

## 4. Dictionary alignment

* **Observed vs Official Dictionary Labels:**
  * **Master Registration:** Column No. 92 in the official spec is named `업종` (column CN). To prevent collision with Column No. 4 (`업종` in column D), pandas loads it as `업종.1`. This is a clean technical adjustment that preserves detailed business type data.
  * **Transaction Supply:** `UDI-DI 일련번호` represents Column No. 28. Standard code is `표준코드(UDI)` (column R), and production identifier is `생산식별자(UDI-PI)` (column S). Observed names align exactly with definitions.
* **Unexpected or Missing Columns:** No unexpected columns were discovered in either workbook; all 93 master and 71 supply columns align with official reference dictionaries.
* **Join-Key Candidates:**
  * Master: `['의료기기품목일련번호', '모델일련번호', 'UDIDI일련번호']`
  * Supply: `['의료기기품목일련번호', '모델일련번호', 'UDI-DI 일련번호']`

## 5. Join feasibility

* **Composite Overlap Counts:**
  * Key combination: `['의료기기품목일련번호', '모델일련번호', 'UDIDI일련번호']` in Master vs `['의료기기품목일련번호', '모델일련번호', 'UDI-DI 일련번호']` in Supply.
  * Unique keys in Master: 221
  * Unique keys in Supply: 100
  * Intersecting keys: Exactly 100 keys. All 100 supply-side unique composite key configurations exist in the master registry.
  * Row-level coverage: Exactly **704,315 joined rows** out of 704,315 transaction supply records (**100.00%**).
* **Multiplicity and Inflation Risk (Extremely Critical):**
  * **Join on `UDI-DI` only:** Yields 738,567 matched rows (**104.86% of supply**). This introduces a **+4.86% artificial row inflation** because identical UDI-DIs are registered under different items/licenses in the master table.
  * **Join on `['의료기기품목일련번호', '모델일련번호']` only:** Yields 1,849,433 matched rows (**262.59% of supply**). This causes a **+162.59% massive row inflation** because the same item + model has multiple packaging configurations (hence multiple UDI-DIs / `UDIDI일련번호`s).
  * **Conclusion:** The full 3-key composite join is **non-negotiable** to prevent severe data duplication and transaction-count inflation.

## 6. Drift and quality flags

* **Master Registry Expiry Gap:** License expiration fields like `유효기간` are entirely unpopulated (100% null) in the Master. Fortunately, the transaction-level `사용기한` (Expiration Date) is **92.97% populated** in the Supply dataset, making it a robust alternative for device age and expiration analysis.
* **Null Country of Origin:** `제조원국가` is 100% null in the Master workbook. For Class 1 import vs domestic classifications, downstream pipelines must rely on the supplier's `업종` = `수입업` as a proxy.
* **Clinical Pricing Integrity:** Although `공급단가` has a global null rate of 21.51%, grouping by `공급형태` shows that transactions heading directly to clinical end-users (`의료기관에 공급` / Supply to Medical Institution) have exceptional coverage: only **7.19% nulls** and **1.96% zeros**. B2B internal distribution transfers are heavily unpriced (35.92% null, 46.67% zero), so pricing anomaly models must filter and isolate hospital-destined transactions.
* **Discard Recipient Integrity:** For `공급구분` = `폐기` (Discard) (1,110 records), 100% of the receiver info columns (`공급받은자`, `공급받은자 사업자등록번호`, and `요양기관기호(의료기관)`) are null, confirming strong internal transaction logic and regulatory compliance.

## 7. Recommended next steps

1. **Mandate 3-Key Joins in Code:** When building the data loader, hardcode the join on `['의료기기품목일련번호', '모델일련번호', 'UDI-DI 일련번호']` (mapping to Master `['의료기기품목일련번호', '모델일련번호', 'UDIDI일련번호']`). Under no circumstances should joins be performed on UDI-DI or model names alone.
2. **Filter by Destination for Anomaly Modeling:** For pricing anomaly detection models, pre-filter the transaction supply dataset on `공급형태` = `의료기관에 공급`. This isolates commercial end-user sales with highly reliable pricing data (90.85% valid and non-zero) and discards B2B distribution transfers.
3. **Use Import Proxy Rule:** Since Master `제조원국가` is 100% unpopulated, use the supplier's `업종` = `수입업` in the transaction supply dataset to segment and analyze imported medical device anomalies.
4. **Utilize Supply Expiry for Lifespan:** Use the Supply dataset's `사용기한` column (92.97% populated) instead of the Master registry's unpopulated `유효기간` fields to build shelf-life expiration violation indicators.
5. **Isolate Discard Transactions:** Isolate `공급구분` = `폐기` (Discard) from recipient flow graphs, as they are confirmed to lack receiving entities.
