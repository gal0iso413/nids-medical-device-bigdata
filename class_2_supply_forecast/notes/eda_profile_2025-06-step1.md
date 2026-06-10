# Data Profile — Wesley Partners NIDS Class 2 Supply Forecast Data Profile Report

> **Agent:** class_2_supply_forecast  
> **Date:** June 5, 2026  
> **Workbooks profiled:** sample_master_registration_data.xlsx, sample_transaction_supply_data.xlsx

## 1. Executive summary

* **Continuous Time-Series Contiguity:** The transaction supply dataset provides a continuous, contiguous **24-month monthly time-series** spanning from January 1, 2024, to December 31, 2025 (730 days) with exactly zero monthly missing gaps, making it highly suitable for rolling window analysis (YoY, MA6, MA12, and moving average deviations).
* **Product & Entity Breadths:** Active products (unique UDI-DIs) remain exceptionally steady at 28 to 36 per month. Supply networks are also stable, with 32 to 49 unique suppliers and 85 to 139 unique receivers reporting transactions each month.
* **High-Quality Expiry Data:** While the Master registry contains 48.63% missing values for `사용기한 사용여부` (Whether Expiration Date is used), the transaction supply dataset has a **99.97% fill rate** for the actual `사용기한` (expiration date) column, enabling high-fidelity inventory depletion and survival-style exhaustion modelling directly from transactional supply records.
* **Import Classification Proxy:** The Master file's `제조원국가` is 100% null. However, in the Supply file, the supplier's `업종` can be used to distinguish direct imports (supplied by entities with `업종` = `수입업`, which includes Becton Dickinson Korea's 3,405 transactions) from domestic distribution (supplied by distributors with `업종` = `판매(임대)업`), providing a clean proxy for import dependency.
* **Absolute Sample Disjointness:** The master registration sample and the transaction supply sample are completely disjoint, with **0.00% physical overlap** on keys. This blocks direct linkage of master-specific covariates (such as product lifecycle age derived from `품목허가일자` and detailed `등급` distributions) to the transaction series.
* **Zero-Price Pricing Volume:** 44.7% of all transaction records (and 54.7% of non-null records) show a unit price of exactly `0.0`, heavily driven by business-to-business transfers. For price and demand time-series models, these must be filtered by `공급형태` to isolate sales to medical institutions where only 3.7% are zero-price.
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

### Date Columns Analysis
* **Master Registration:**
  * `품목허가일자` (Approval Date): `str` (formatted as YYYY-MM-DD, e.g. `'2016-11-16'`), Null rate: 0.00%. Highly suitable for calculating product life-cycle age (Elapsed Time = Supply Date - Approval Date) once parsed.
* **Transaction Supply:**
  * `공급일자` (Supply Date): `int64` (formatted as YYYYMMDD, e.g. `20240102`), Null rate: 0.00%. Must be parsed via `pd.to_datetime(s_df['공급일자'].astype(str), format='%Y%m%d')` for time-series aggregation.

### Supply Quantity and Amount Series (Monthly Aggregations)
The transaction supply dataset provides a complete 24-month (Jan 2024 to Dec 2025) contiguous series with the following aggregations:
* **Monthly transaction count:** Ranges from 383 (Dec 2025) to 720 (Aug 2025).
* **Monthly total supply quantity:** Ranges from 399 (Dec 2025) to 802 (Aug 2025). Mean quantity per transaction is highly stable at 1.14 (std: 0.50).
* **Monthly total supply amount:** Ranges from 279,969,682 KRW (Sep 2024) to 699,801,015 KRW (Aug 2025). Mean amount per transaction is 892,640.37 KRW (std: 1,245,894.80 KRW).

### Covariate Fields and Disruption Signals
* **Device Class (`등급`):**
  * Master: `int64`, 0.00% Null, distribution: `{Class 1: 231, Class 3: 223, Class 2: 50, Class 4: 6}`.
  * Supply: `int64`, 0.00% Null, distribution: `{Class 4: 12,558}`. (All rows in Supply represent high-risk Class 4 items).
* **Implantable Status (`인체이식형 여부`):**
  * Master (`인체이식 의료기기 여부`): `str`, 0.00% Null, distribution: `{'N': 282, 'Y': 228}`.
  * Supply (`인체이식형 의료기기여부`): `str`, 0.00% Null, distribution: `{'예': 12,558}`. (All supply transactions represent implantable devices).
* **Traceable Device (`추적관리대상`):**
  * Master (`추적관리대상 의료기기 여부`): `str`, 0.00% Null, distribution: `{'N': 506, 'Y': 4}`.
  * Supply (`추적관리대상`): `str`, 0.00% Null, distribution: `{'아니오': 12,558}`.
* **Orphan Device (`희소의료기기`):**
  * Master (`희소의료기기 여부`): `str`, 0.00% Null, distribution: `{'아니오': 510}`.
  * Supply (`희소의료기기여부`): `str`, 0.00% Null, distribution: `{'아니오': 12,558}`.
* **Export Only (`수출용여부`):**
  * Master (`수출용 여부`): `str`, 0.00% Null, distribution: `{'아니오': 510}`.
  * Supply (`수출용여부`): `str`, 0.00% Null, distribution: `{'아니오': 12,558}`.
* **Expiry Management (`사용기한`):**
  * Master (`사용기한 사용여부`): `str`, **48.63% Null**, distribution: `{nan: 248, 'Y': 235, 'N': 27}`.
  * Supply (`사용기한`): `float64` (YYMMDD format), **0.03% Null** (practically fully populated), sample: `[250901.0, 250811.0, 250721.0, 250727.0, 240805.0]`.

## 4. Dictionary alignment

* **Master Registration Alignment:**
  * Duplicate dictionary entry for `업종` (Column D and CN) is resolved in pandas by loading Column CN as `업종.1`. All 93 columns map perfectly.
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
  * Overlapping standard identifiers (`UDI-DI` ↔ `UDIDI` after standardizing type and strip leading zeros): **0 rows (0.00% overlap)**
* **Join Blockers:**
  * Complete sample population mismatch. The master registry contains no rows for the single device category (`말초혈관용그라프트스텐트` - peripheral vascular graft stents) reported in the supply transactions.
  * A physical join between these two worksheets returns **0 rows**.
  * This blocks the direct linkage of master-specific covariates (like product lifecycle age derived from `품목허가일자` and detailed `등급` distributions) to the transaction series.

## 6. Drift and quality flags

* **Pandas Auto-Renaming Drift:** Any ingestion pipeline must be prepared to look for `업종.1` instead of `업종` for CN, or explicitly rename it, to prevent column key-error issues.
* **High-Quality Expiry Date in Transactions:** The extremely high fill-rate (99.97%) for `사용기한` in the Supply sheet means survival and exhaustion forecasting can bypass the 48.63% missingness in the Master file's `사용기한 사용여부` column.
* **Import Classification Proxy:** Since `제조원국가` is 100% null in the Master file, we can classify transactions into direct imports (`업종` = `수입업` in Supply) vs domestic distribution (`업종` = `판매(임대)업` in Supply). This provides a clean proxy for import dependency.
* **Zero-Price Pricing Volume:** 44.7% of all transaction records (and 54.7% of non-null records) show a unit price of exactly `0.0`, heavily driven by business-to-business transfers (`제조ㆍ수입ㆍ판매(임대)에 공급` has 70.1% zero-pricing). For price and demand time-series models, these must be filtered by `공급형태` to isolate sales to medical institutions where only 3.7% are zero-price.

## 7. Recommended next steps

1. **Leverage Supply Expiry Date Directly:** Build survival models (Kaplan-Meier and Cox Proportional Hazard) utilizing the highly populated `사용기한` column in Supply for tracking exhaustion timelines, bypassing the sparse Master file registry.
2. **Utilize Supplier Business Type as Import Proxy:** Use the supplier's `업종` = `수입업` as a binary flag for Import Dependency in modeling supply chain vulnerability covariates.
3. **Price Filter for Forecasting Models:** Restrict price/demand time-series forecasting models (like moving averages or LSTM/SARIMA) to transactions where `공급형태` is `의료기관에 공급` to avoid being skewed by the zero-price B2B transactions.
4. **Construct Mock Join-Mappings:** Since the sample worksheets are physically disjoint, any unified forecasting model testing in Phase 1-2 must utilize simulated link mapping parameters (e.g. mappingTaewoong or GS Medical items to Becton Dickinson transactions) or await aligned production datasets.
5. **Halt for PM Approval:** In accordance with the Phase 1 lock, do not write modeling or time-series scripts in `src/` or advance to Phase 2 until the PM reviews this profile and approves the advancement.
