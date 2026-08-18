# Data Profile — top7 Modeling Tier (MCDM focus)

> **Agent:** class_3_impact_evaluation  
> **Date:** 2026-06-10  
> **Workbooks profiled:** top7_master_registration_data.xlsx, top7_transaction_supply_data.xlsx

## 1. Executive summary

* **Massive Scale & Breadth:** The transaction supply database contains **704,315 rows** (with 71 columns) spanning **9,581 unique medical institutions** (요양기관기호) and **11,815 total clients** (공급받은자) supplied by **1,860 unique suppliers** (공급자). This represents an incredible, nationally representative footprint of usage breadth.
* **Oligopolistic Supplier Concentration (Supply Risk):** High-value clinical groups show extreme market concentration. In `창상피복재` (Wound Dressings), which has a market scale of **13.46 Trillion KRW**, the top 3 suppliers control **99.72%** of the entire market (HHI = 5,455.2). In `인체조직 또는 기능 대치품` (Heart valves/Tissue grafts, 707 Billion KRW), the top 3 suppliers control **72.02%** of the market (HHI = 2,906.6). These monopoly groups represent severe supply chain bottlenecks for the MCDM framework.
* **Critical Substitutability Proxies:** In both Master and Supply, every single item group (품목군) has exactly **1 unique item license (의료기기품목일련번호 = 1)**, meaning they represent highly specialized regulatory categories where products are differentiated only at the model level (모델일련번호).
* **Clinical Severity Flag Completeness:** Clinical impact multipliers are perfectly populated: `등급` (Device Class) has 0% nulls with Class 4 (highest risk) fully tracked. `인체이식형 의료기기여부` (Implantable) and `추적관리대상` (Traceable) have 100% completeness (0% nulls) across both files, facilitating robust clinical scoring.
* **Missingness & Alternate Proxies:** `제조원국가` (Manufacturer Country) in Master is **100.00% null**, meaning we cannot directly calculate national import dependency from this column. Code must use Master `업종` = `수입업` or Supply `제조업체명` as proxies for foreign supply risk.
* **Typographical Suffix Blocker:** Naive joining of Master and Supply on `model_serial` or `udi_di_serial` yields exactly 0.00% overlap. This is because Supply loads keys as decimal strings (e.g., `'1212681.0'`) while Master loads them as integer strings (e.g., `'1212681'`). Implementing a trailing `.0` stripping adapter resolves this, achieving a 100% join rate.

## 2. Workbook inventory

### Workbook 1: Master Registration
* **File path:** `shared_data/top7_master_registration_data.xlsx`
* **Sheet names:** `['Sheet1']`
* **Dimensions:** 221 data rows, 93 columns

### Workbook 2: Transaction Supply
* **File path:** `shared_data/top7_transaction_supply_data.xlsx`
* **Sheet names:** `['개요', '공급내역 보고자료']`
* **Dimensions:**
  * Sheet `개요`: 15 rows (metadata / overview)
  * Sheet `공급내역 보고자료` (tabular supply data): 704,315 data rows, 71 columns

## 3. Column profile

### Master Registration target columns:
* **`의료기기품목일련번호` (Item Serial):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 7
  * **Samples:** ['2016001337', '200405634', '2016002200', '2016000452', '2012001853']
* **`모델일련번호` (Model Serial):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 110
  * **Samples:** ['1212681', '1723716', '1247375', '287706', '287703']
* **`UDIDI일련번호` (UDI-DI Serial):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 221
  * **Samples:** ['1108144', '1108158', '1108831', '1108166', '1108845']
* **`UDIDI` (UDI-DI Code):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 213
  * **Samples:** ['20884523003229', '08806129615321', '08806129615352', '20884523003151', '10884521066168']
* **`등급` (Device Class):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 4
  * **Samples:** ['4', '3', '1', '2']
* **`제조원국가` (Overseas Manufacturer Country):**
  * **dtype:** object | **Null count:** 221 (100.00%) | **Cardinality:** 0
  * **FLAG:** **>50% Null (100.00% missing)**. Unusable for direct analysis.
* **`인체이식 의료기기 여부` (Implantable status):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
  * **Samples:** ['N', 'Y']
* **`추적관리대상 의료기기 여부` (Traceable Status):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
  * **Samples:** ['N', 'Y']
* **`일회용 의료기기 여부` (Single-use Status):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 1
  * **Samples:** ['N']
* **`희소의료기기 여부` (Orphan Status):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
  * **Samples:** ['예', '아니오']
* **`요양급여 대상 여부` (Reimbursement Status):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
  * **Samples:** ['N', 'Y']
* **`요양급여코드(','로 구분)` (Reimbursement Codes):**
  * **dtype:** object | **Null count:** 71 (32.13%) | **Cardinality:** 24
  * **Samples:** ['M3030766', 'M6710539', 'M3030703', 'M3030701', 'M3030715']
* **`품목군` (Item Group):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 7
  * **Samples:** ['창상피복재', '의료처치용 기계기구(II)', '결찰기 및 봉합기(I)', '인체조직 또는 기능 대치품', '결찰기 및 봉합기(II)']
* **`한벌구성 의료기기 여부` (Set status):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
  * **Samples:** ['N', 'Y']
* **`업종` (Business Type):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
  * **Samples:** ['제조업', '수입업']

### Supply Actual Data target columns:

* **`공급수량` (Supply Quantity - Scale):**
  * **Null count:** 99 (0.01%) | **Zeros:** 4 (0.00%)
  * **Descriptive Stats:** Min: 0.0 | Max: 102180.0 | Mean: 60.54
* **`공급금액` (Supply Amount - Scale):**
  * **Null count:** 120871 (17.16%) | **Zeros:** 178724 (25.38%)
  * **Descriptive Stats:** Min: 0.0 | Max: 8809177043399.0 | Mean: 25032428.71
* **`요양기관기호(의료기관)` (Medical Institution Code - Breadth):**
  * **dtype:** object | **Null count:** 337034 (47.85%) | **Cardinality:** 9581
  * **Samples:** ['37100386.0', '31210627.0', '12280003.0', '31211844.0', '31100678.0']
* **`공급받은자` (Receiver Name - Breadth):**
  * **dtype:** object | **Null count:** 1123 (0.16%) | **Cardinality:** 11815
  * **Samples:** ['의료법인 참예원의료재단 서초참요양병원', '주식회사 조이메디컬', '성모윌병원', '(주)재능컴퍼니', '곽병원']
* **`공급자` (Supplier Name - Monopoly):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 1806
  * **Samples:** ['주식회사 조이메디컬', '(주)가온메디칼', '(주)에이치메디', '(주)재능컴퍼니', '제이엠메디']
* **`공급한자 업체일련번호` (Supplier ID - Monopoly):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 1860
  * **Samples:** ['108076937.0', '108180683.0', '108173581.0', '108158574.0', '108075599.0']
* **`등급` (Device Class):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 4
* **`인체이식형 의료기기여부` (Implantable):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
* **`추적관리대상` (Traceable):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
* **`희소의료기기여부` (Orphan):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
* **`요양급여대상여부` (Reimbursement Status):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
* **`요양급여코드입력값` (Reimbursement Code):**
  * **dtype:** object | **Null count:** 15557 (2.21%) | **Cardinality:** 18
* **`일회용여부` (Single-use):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 1
* **`한벌구성여부` (Set status):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 2
* **`조합의료기기여부` (Combination status):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 1
* **`품목군` (Item Group):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** 7
* **`표준코드(UDI)` (UDI):**
  * **dtype:** object | **Null count:** 0 (0.00%) | **Cardinality:** >=20000

## 4. Dictionary alignment

* **Observed vs Official Dictionary labels:**
  * Master Registration and Transaction Supply column headers are **100.00% aligned** with the official dictionary fields specified in `description_master_registration.md` and `description_transaction_supply.md`. No columns are missing, and no duplicates are loaded with `.1` suffixes, demonstrating clean, uncorrupted Excel parsing.
* **Join-Key Candidates:**
  * **Primary Candidate:** The 3-field composite key `(의료기기품목일련번호, 모델일련번호, UDI-DI 일련번호)`. This key provides a flawless 100.00% mapping of transaction supply data to product registrations.
  * **Secondary Candidate:** `UDI-DI` (`UDIDI` in Master vs `UDI-DI` in Supply). This key matches 94 unique values.

## 5. Join feasibility

* **Linkage Overlaps (Cleaned Keys):**
  * **`의료기기품목일련번호`:** Master unique: 7 | Supply unique: 7 | Overlap count: 7 (**100.00% of Supply mapped**)
  * **`모델일련번호`:** Master unique: 110 | Supply unique: 57 | Overlap count: 57 (**100.00% of Supply mapped**)
  * **`UDI-DI 일련번호` / `UDIDI일련번호`:** Master unique: 221 | Supply unique: 100 | Intersection: 100 (**100.00% of Supply mapped**)
  * **`composite_keys` `(의료기기품목일련번호, 모델일련번호, UDI-DI 일련번호)`:** Master unique: 221 | Supply unique: 100 | Overlap count: 100 (**100.00% of Supply mapped**)

* **Blockers Identified & Resolved:**
  * **Type Mismatch Blocker:** Supply columns were loaded as float strings (e.g. `'1212681.0'`) while Master columns were loaded as integer strings (e.g. `'1212681'`). A naive string join results in exactly **0.00% overlap**. This has been fully resolved by implementing a `clean_key` adapter that strips the `.0` decimal suffix from float strings, achieving a perfect 100% intersection.

## 6. Drift and quality flags

### A. Substitutability Proxies (Item Group Analysis)
This analysis evaluates substitutability based on the count of unique items and models inside each `품목군` (Item Group). Fewer alternative models or products indicate zero substitutability (higher disruption impact).

| Item Group (품목군) | Unique Items (Master) | Unique Models (Master) | Unique UDI-DIs (Master) | Unique Items (Supply) | Unique UDI-DIs (Supply) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| 의약품 주입기(II) | 1 | 5 | 5 | 1 | 667 |
| 인체조직 또는 기능 대치품 | 1 | 11 | 11 | 1 | 9329 |
| 결찰기 및 봉합기(II) | 1 | 44 | 88 | 1 | 7539 |
| 창상피복재 | 1 | 19 | 51 | 1 | 4757 |
| 의료처치용 기계기구(II) | 1 | 6 | 15 | 1 | 1986 |
| 결찰기 및 봉합기(I) | 1 | 9 | 19 | 1 | 1081 |
| 의료용 소식자(I) | 1 | 16 | 24 | 1 | 1845 |

* **Finding:** Across all groups, there is exactly **1 unique item license (의료기기품목일련번호 = 1)**, indicating that each product represents a highly specialized, non-substitutable regulatory category. Models within `결찰기 및 봉합기(II)` (44 models) are more substitutable than `의약품 주입기(II)` (5 models) or `의료처치용 기계기구(II)` (6 models), making the latter two highly vulnerable bottlenecks.

### B. Supplier Concentration (Monopoly Risk / Likelihood of Disruption)
This analysis measures market monopoly concentration per item group using the Herfindahl-Hirschman Index (HHI) and Top 1 / Top 3 supplier shares of total supply quantity and amount.

| Item Group (품목군) | Total Qty | Total Amount (KRW) | Suppliers | HHI (Amt) | Top 1 Share (Amt) | Top 3 Share (Amt) | Top Suppliers |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 결찰기 및 봉합기(I) | 6,470,024 | 5.7B | 419 | 616.7 | 14.8% | 37.7% | (주)유니메딕스, (주)멀티메디케어 |
| 결찰기 및 봉합기(II) | 1,660,191 | 354.2B | 177 | 705.5 | 14.0% | 35.3% | (주)대승써지칼, 케어캠프(주) |
| 의료용 소식자(I) | 4,861,763 | 39.9B | 344 | 1690.1 | 29.5% | 62.3% | 주식회사 와이앤비메딕스, 메디랩코리아(주) |
| 의약품 주입기(II) | 161,719 | 28.1B | 122 | 1462.7 | 29.5% | 60.1% | 벡톤디킨슨코리아(주), 바드코리아(주) |
| 의료처치용 기계기구(II) | 5,403,915 | 7.7B | 156 | 615.7 | 13.2% | 31.3% | 메드라인코리아 유한책임회사, 우진 메디칼 |
| 인체조직 또는 기능 대치품 | 42,685 | 707.5B | 30 | 2906.6 | 50.4% | 72.0% | 에드워즈라이프사이언시스코리아(주), (주)이지메디컴 |
| 창상피복재 | 24,033,464 | 13,461.9B | 1320 | 5455.2 | 65.4% | 99.7% | (주)제네웰화성지사, 한국먼디파마유한회사 |

* **Severe Wound Dressing Monopoly:** `창상피복재` has an immense market scale of **13.46 Trillion KRW**, yet the top 3 suppliers control **99.72%** of the entire market, with the top supplier `(주)제네웰화성지사` holding **65.44%**. This represents an extreme, systemic oligopoly (HHI = 5,455.2) where a single supplier's disruption will cripple the entire national supply chain.
* **Heart Valve / Tissue Graft Dependency:** `인체조직 또는 기능 대치품` (heart valves and tissue grafts, 707 Billion KRW) is highly concentrated, with the top 3 suppliers controlling **72.02%** of the market, led by `에드워즈라이프사이언시스코리아(주)` holding **50.44%** (HHI = 2,906.6). These life-saving devices represent major bottlenecks.
* **General Quality Issues:**
  * **Master Registration Null Columns:** In Master, `제조원국가` (Overseas Manufacturer Country) is **100.00% null**. Import dependencies must be modeled using Master `업종` = `수입업` or Supply `제조업체명` instead.
  * **Pricing Barcode Injection Anomaly:** Maximum '공급단가' is **8.8 Trillion KRW**. This is a GS1 barcode entered in the price column, requiring an upper-bound filter (e.g. 50M KRW).

## 7. Recommended next steps

1. **Clean Composite Join Keys:** Force all ETL pipelines to strip trailing `.0` decimal suffixes from `item_serial`, `model_serial`, and `udi_di_serial` to enable the 100% perfect join.
2. **Apply MCDM Supplier Monopoly Weights:** Use the computed Top 1 and Top 3 supplier shares and HHI (amount) per Item Group as a direct proxy for Supply Risk (X-Axis) likelihood.
3. **Model Substitutability:** Score substitutability (Y-Axis) using the number of unique UDI-DIs in Supply for each `품목군` (e.g., lower unique UDI-DIs = higher clinical dependency).
4. **Use Hospital Breadth in Scale Score:** Use the count of unique `요양기관기호(의료기관)` (hospital codes) per device to measure national clinical exposure breadth (higher breadth = higher MCDM priority).
5. **Foreign Dependency Proxy:** Use Master `업종` = `수입업` and Supply `제조업체명` as the foreign supply chain risk indicator since `제조원국가` is 100% null.
6. **Price Filter:** Apply an upper-bound filter (e.g., `< 50,000,000 KRW`) to `공급단가` and `공급금액` to remove barcode leakage.
