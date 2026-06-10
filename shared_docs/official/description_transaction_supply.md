# Medical Device Supply Details Report — Data Dictionary (Official Reference)

> **Status:** Authoritative field specification (converted from NIDS/MFDS supply-details data dictionary).
> **Edit policy:** PM-maintained official log; agents **read-only**. Do not modify.
> **Companion data:** `shared_data/sample_transaction_supply_data.xlsx` (sample tier); `shared_data/top7_transaction_supply_data.xlsx` (modeling tier — sheet 2 `공급내역 실제자료` only; sheet 1 `표지`/개요 is metadata).
> **Related official doc:** `description_master_registration.md` (join via UDI-DI / item / model serial numbers).

## Purpose of this document

Defines every column in **medical device supply details report data** (공급내역보고): regulatory meaning, mandatory rules, linkage to integrated registration data, and Wesley Partners **Class 1** analytic groupings. Use when interpreting transaction/supply samples or production supply extracts.

## Relationship to `shared_data/`

| Artifact | Role |
|----------|------|
| `sample_transaction_supply_data.xlsx` | Executable sample rows for Agent 1 (anomaly) and Agent 2 (forecast) |
| `top7_transaction_supply_data.xlsx` | Modeling-tier supply rows (7 licenses); ingest sheet 2 `공급내역 실제자료` only |
| This file | Semantic authority for column labels, keys, and business rules — not a fixed runtime schema |

Agents must follow **dynamic ingestion** in `shared_data/DATA_LAYER.md`: discover columns, profile dtypes/nulls, and adapt to drift; treat the table below as reference, not hardcoded code constants.

## Agent usage

| Agent | When to consult |
|-------|-----------------|
| Class 1 — Anomaly | Supply graph edges, pricing, supply classification, receiver null rules (e.g. discard) |
| Class 2 — Forecast | Supply date, quantity, unit price, amount, base month, entity identifiers |
| Class 3 — Impact | Transaction amounts and policy-sensitive flags (reimbursement, traceability) |

**Hierarchy of truth:** `shared_docs/structured/class_*_spec.md` overrides `official/` for assigned agent analytical work; this file supplies **field definitions** when profiling sample/prod supply files.

## Keys and linkage (quick reference)

| Concept | Fields / rule |
|---------|----------------|
| Row identity | `SupplyDetailsReportDataCompositeKey` = Client Code (BK) + Supply Details Base Month (AZ) + Work Serial (BA) + Supply Serial (BB) |
| Join to master registration | Medical Device **Item Serial** (T), **Model Serial** (BI), **UDI-DI Serial** (AB) ↔ integrated registration keys |
| Data item categories | Supplier Information · Receiver Information · Supplied Medical Device Information · Supply Information |
| Discard supply | If supply classification is **Discard**, receiver information does not exist |

## Document map

1. **Data item structure** — categories and linkage rules (below).
2. **Data item specification** — full column table (No. 1–71, Excel columns A–BS).

---

## Data item structure and description

### Data Item Structure and Description (Supply Details Report Data)

* The supply details report data includes data items used for data management in addition to the data in the supply details report format.

* Data Item Category (Column F): Consists of [Supplier Information / Receiver Information / Supplied Medical Device Information / Supply Information].
  * Supplier Information: Information linked from [Integrated Company] based on the [Company Serial Number] key value.
  * Receiver Information: Information linked from [Client Information] based on the [Client Code] key value / The client code is a unique code generated per client when registering clients by company.
  * Supplied Medical Device Information: Information linked from [Integrated Information] based on the [UDI-DI Serial Number / Item Serial Number / Model Serial Number] key values corresponding to the UDI-DI entered during supply reporting.
  * Supply Information: Data generated during the input process when preparing the supply details report data.
* If Supply Classification is (Discard), receiver information does not exist.
* Key value distinguishing [Medical Device Supply Details Report Data] = Distinguished by the combination of SupplyDetailsReportDataCompositeKey.
* Linked key value data between [Medical Device Supply Details Report Data] and [Medical Device Integrated Information Registration Data] = Medical Device Item Serial Number / Model Serial Number / UDIDI Serial Number.

---

### Data Item Specification

| No. | Data Item Name | Excel Column | Data Item Description | Data Item Category | Included in Report Format | Mandatory Input Type | Class 1 (* Wesley Partners 1st Classification) | Class 2 (Comments on Changes, etc.) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 연번 | A | Display order when exporting supply details report data to Excel | - | X | - | - | |
| 2 | 공급자 | B | Name of the company that supplied the medical devices (Supply reporting entity) | Supplier Information | O | - | Transaction Entity & Identification Info | |
| 3 | 업허가번호 | C | Manufacturing/Importing business license number if the supplier's business type is manufacturer or importer.<br>* Supply reporting is conducted per business license, and if the license numbers (approval/report numbers) differ, they are classified as different companies even if the company names are identical. | Supplier Information | O | - | - | |
| 4 | 업종 | D | Business type of the supplier | Supplier Information | O | - | Transaction Entity & Identification Info | |
| 5 | 공급한자 업체일련번호 | E | Company serial number of the supplier | Supplier Information | X | - | Transaction Entity & Identification Info | |
| 6 | 공급구분 | F | Classification based on the criteria for supplying medical devices (Input value: Choose 1 among Issue/Return/Discard/Lease/Recall) | Supply Information | O | Mandatory | Transaction Attribute & Amount Info | |
| 7 | 공급형태 | G | Value entered according to the business type of the receiving company.<br>* Input value (Choose 1 among the 4 below):<br>1. Supply to Manufacturer/Importer/Seller(Leaser)<br>2. Supply to Medical Institution<br>3. Supply to Pharmacy Founder or Pharmaceutical Wholesaler<br>4. Supply for Samples, Donations, or Military use<br>* However, if supplied for samples, donations, or military use, select [4. Supply for Samples, Donations, or Military use] regardless of the receiving company's business type. | Supply Information | O | Mandatory | Transaction Attribute & Amount Info | |
| 8 | 대표자명 | H | Name of the representative of the supplying company.<br>* Item entered upon membership registration. | Supplier Information | X | - | - | |
| 9 | 사업자등록번호 | I | Business registration number of the supplying company.<br>* Item entered upon membership registration. | Supplier Information | O | - | Transaction Entity & Identification Info | |
| 10 | 공급받은자 | J | Name of the receiving company.<br>* (Reference) Company information retrieved during client search:<br>- Sales(Lease) business: A company registered as a medical device sales(lease) business at the competent public health center.<br>- Medical Institution: A company registered as a medical institution with the Health Insurance Review & Assessment Service. | Receiver Information | O | - | Transaction Entity & Identification Info | |
| 11 | 요양기관기호(의료기관) | K | Medical institution symbol if the receiving company's business type is a medical institution.<br>* Information linked during client search; requires confirmation if null. | Receiver Information | O | - | Transaction Entity & Identification Info | |
| 12 | 업허가번호(의료기기판매,임대업) | L | Medical device sales(lease) business license number if the supplier's business type is a medical device sales(lease) business.<br>* Supply reporting is conducted per business license, and if the license numbers (approval/report numbers) differ, they are classified as different companies even if the company names are identical. | Receiver Information | O | - | - | |
| 13 | 공급받은자업종 | M | Business type of the receiving company.<br>* However, if the supplier selects 'Other' and manually registers the client, the company information is not linked, so 'Business Type' is not reflected.<br>- Manual registration as 'Other' is only allowed for supply reporting before the receiving company's info is linked, and must be updated with the retrieved company info after linkage. | Receiver Information | X | - | Transaction Entity & Identification Info | |
| 14 | 공급받은자 업종 상세 | N | Detailed classification of the receiving company's business type.<br>* Sales(Lease) business: Classified into [Medical Device, General Comprehensive Wholesale], and reflected as 'General Comprehensive Wholesale' if they possess a pharmaceutical wholesale license. | Receiver Information | X | - | Transaction Entity & Identification Info | |
| 15 | 공급받은자 업체일련번호 | O | Company serial number of the receiving company | Receiver Information | X | - | - | |
| 16 | 공급받은자대표자명 | P | Name of the representative of the receiving company | Receiver Information | X | - | - | |
| 17 | 공급받은자 사업자등록번호 | Q | Business registration number of the receiving company.<br>* Information linked during client search; may be null since supply reporting classifies companies based on business license. | Receiver Information | O | - | Transaction Entity & Identification Info | |
| 18 | 표준코드(UDI) | R | Supplied medical device standard code (UDI-DI + UDI-PI) | Supply Information | O | Mandatory | Product & Code Info | Distribution & Production History Info<br>(UDI-PI is not entered during integrated info registration and relates to distribution history) |
| 19 | 생산식별자(UDI-PI) | S | Supplied medical device production identifier (UDI-PI).<br>* Production Identifier:<br>- Information related to the production of individual medical devices; can be omitted for Class 1 medical devices or user-sterilized orthopedic supplies used in set configurations (all classes).<br>- (10) Lot Number, (11) Date of Manufacture, (17) Expiration Date, (21) Serial Number. | Supply Information | O | Conditionally Mandatory<br>(Mandatory input unless it's a Class 1 medical device or a user-sterilized orthopedic medical device used in a set configuration) | Product & Code Info | Distribution & Production History Info<br>(UDI-PI is not entered during integrated info registration and relates to distribution history) |
| 20 | 의료기기품목일련번호 | T | Serial number uniquely assigned per medical device item license.<br>* Can have two or more item serial numbers even with the same UDI-DI.<br>- Example) When using the UDI attached by an overseas manufacturer as-is, there might be two or more companies registering integrated info with the same UDI-DI, but since item licenses differ, they can be distinguished by item serial number. | Supplied Medical Device Information | X | - | Product & Code Info | |
| 21 | 품목분류번호 | U | Code assigned per medical device item, 1 English letter + 5 digits + . + 2 digits.<br>* English code: [Apparatus/Machine(A), Medical Supply(B), Dental Material(C)] | Supplied Medical Device Information | O | - | Product & Code Info | |
| 22 | 제조업체명 | V | Name of the company that manufactured (imported) the supplied medical device (License information) | Supplied Medical Device Information | X | - | Product & Code Info | |
| 23 | 품목명 | W | Item name of the supplied medical device (License information) | Supplied Medical Device Information | O | - | Product & Code Info | |
| 24 | 등급 | X | Grade of the supplied medical device (License information) | Supplied Medical Device Information | X | - | Product & Code Info | |
| 25 | 품목허가번호 | Y | Item license number of the supplied medical device (License information) | Supplied Medical Device Information | X | - | Product & Code Info | |
| 26 | 모델명 | Z | Model name of the supplied medical device (License information) | Supplied Medical Device Information | O | - | Product & Code Info | |
| 27 | UDI-DI | AA | Unique Device Identifier (UDI-DI) of the supplied medical device | Supplied Medical Device Information | O | - | Product & Code Info | |
| 28 | UDI-DI 일련번호 | AB | Serial number uniquely assigned per UDI-DI | Supplied Medical Device Information | X | - | - | |
| 29 | 로트번호 | AC | Lot number among the medical device production identifiers (UDI-PI).<br>A number marked so that all matters regarding manufacturing management and shipment can be verified for a specific manufacturing lot. | Supply Information | O | Conditionally Mandatory<br>(Mandatory if corresponding item information is included in Column S) | Distribution & Production History Info | |
| 30 | 일련번호 | AD | Serial number among the medical device production identifiers (UDI-PI).<br>A number assigned one by one to each medical device to identify individual medical devices. | Supply Information | O | Conditionally Mandatory<br>(Mandatory if corresponding item information is included in Column S) | Distribution & Production History Info | |
| 31 | 제조연월 | AE | Date of manufacture among the medical device production identifiers (UDI-PI).<br>The date the medical device was manufactured (YYMMDD), meaning the same as the manufacturing date. | Supply Information | O | Conditionally Mandatory<br>(Mandatory if corresponding item information is included in Column S) | Distribution & Production History Info | |
| 32 | 사용기한 | AF | Expiration date among the medical device production identifiers (UDI-PI).<br>The deadline until which the product can be used (YYMMDD). | Supply Information | O | Conditionally Mandatory<br>(Mandatory if corresponding item information is included in Column S) | Distribution & Production History Info | |
| 33 | 공급일자 | AG | Date the medical device was supplied (YYMMDD) | Supply Information | O | Mandatory | Transaction Attribute & Amount Info | |
| 34 | 공급수량 | AH | Quantity of medical devices supplied.<br>* UDI-DI is generated differently per inner packaging quantity (the number of single pieces inside one package), and inputted based on the packaging unit registered in UDI-DI. | Supply Information | O | Mandatory | Transaction Attribute & Amount Info | |
| 35 | 포장내 총 수량 | AI | Number of single pieces within the packaging unit registered for the corresponding UDI-DI. | Supplied Medical Device Information | O | - | - | Product & Code Info<br>(Since UDI-DI is generated differently per packaging unit, the number of single pieces per packaging unit is required) |
| 36 | 포장내수량 중 낱개 회수수량 | AJ | If 'Recall' is entered in the 'Supply Classification' item and products are recalled by single piece unit, the quantity of single pieces recalled.<br>* Example) If 1 box (10ea/box) was supplied but only 5ea were recalled, enter 5 for the single piece recall quantity. | Supply Information | X | Optional | - | |
| 37 | 공급단가 | AK | Supply unit price per packaging unit in the integrated info registered for the corresponding UDI-DI. | Supply Information | O | Conditionally Mandatory<br>(Mandatory input when supplying reimbursable treatment material medical devices to medical institutions) | Transaction Attribute & Amount Info | |
| 38 | 공급금액 | AL | Total amount of medical devices supplied (Supply Quantity (Column AH) * Supply Unit Price (Column AK)). | Supply Information | O | Conditionally Mandatory<br>(Mandatory input when supplying reimbursable treatment material medical devices to medical institutions) | Transaction Attribute & Amount Info | |
| 39 | 추적관리대상 | AM | Whether the item registered with the corresponding UDI-DI is a 'traceability management target medical device' (License information) | Supplied Medical Device Information | X | - | - | |
| 40 | 사용자멸균정형용품여부 | AN | Whether the model registered with the corresponding UDI-DI corresponds to orthopedic supplies sterilized and used by the user | Supplied Medical Device Information | X | - | - | |
| 41 | 세트화구성여부 | AO | Whether the model registered with the corresponding UDI-DI is configured into a set for convenience of use in medical institutions, among user-sterilized orthopedic supplies | Supplied Medical Device Information | X | - | - | |
| 42 | 중고의료기기포함여부 | AP | Whether the item registered with the corresponding UDI-DI includes used medical devices (License information) | Supplied Medical Device Information | X | - | - | |
| 43 | 희소의료기기여부 | AQ | Whether the item registered with the corresponding UDI-DI corresponds to an 'orphan medical device' (License information) | Supplied Medical Device Information | X | - | - | |
| 44 | 요양급여대상여부 | AR | Whether the model registered with the corresponding UDI-DI corresponds to a 'reimbursable treatment material medical device' | Supplied Medical Device Information | X | - | Transaction Attribute & Amount Info | Product & Code Info<br>(Information attribute regarding the medical device product) |
| 45 | 요양급여코드입력값 | AS | Reimbursable code entered when the model registered with the corresponding UDI-DI corresponds to a 'reimbursable treatment material medical device' (Fixed rate, benefit code) | Supplied Medical Device Information | X | - | Transaction Attribute & Amount Info | Product & Code Info<br>(Information attribute regarding the medical device product) |
| 46 | 비고 | AT | Text written in the 'Remarks' section by the supplying company when inputting supply report data | Supply Information | O | Optional | - | |
| 47 | 공급받은자의 소재지 상세 | AU | Detailed address of the receiving company | Receiver Information | X | - | Transaction Entity & Identification Info | |
| 48 | 공급받은자의 소재지 시도코드 | AV | Regional classification of the receiving company's address | Receiver Information | X | - | - | |
| 49 | 공급한자의 소재지 상세 | AW | Detailed address of the supplying company | Supplier Information | X | - | Transaction Entity & Identification Info | |
| 50 | 공급한자의 소재지 시도코드 | AX | Regional classification of the supplying company's address | Supplier Information | X | - | - | |
| 51 | 인체이식형 의료기기여부 | AY | Whether the item registered with the corresponding UDI-DI corresponds to an 'implantable medical device' (License information) | Supplied Medical Device Information | X | - | - | |
| 52 | 공급내역기준연월 | AZ | Base year and month entered on the supply date (YYYYMM) | Supply Information | O | - | System Management Info | |
| 53 | 공급내역작업일련번호 | BA | Report sequence number accumulated in the report data registration table and supply report table when the supplying company completes reporting the corresponding report data | Supply Information | X | - | - | |
| 54 | 공급내역일련번호 | BB | Serial number per case according to the report work serial number under which the supplying company registered the corresponding report data | Supply Information | X | - | System Management Info | |
| 55 | 일회용여부 | BC | Whether the item registered with the corresponding UDI-DI is 'single-use' (License information) | Supplied Medical Device Information | X | - | - | |
| 56 | 한벌구성여부 | BD | Whether the item registered with the corresponding UDI-DI corresponds to a 'set configuration medical device' (License information) | Supplied Medical Device Information | X | - | - | |
| 57 | 조합의료기기여부 | BE | Whether the item registered with the corresponding UDI-DI corresponds to a 'combination medical device' (License information) | Supplied Medical Device Information | X | - | - | |
| 58 | 품목취소취하여부 | BF | Whether the item license registered with the corresponding UDI-DI has been canceled/withdrawn/expired (License information) | Supplied Medical Device Information | X | - | - | |
| 59 | 수출용여부 | BG | Whether the item registered with the corresponding UDI-DI corresponds to an 'export-use medical device' (License information) | Supplied Medical Device Information | X | - | - | |
| 60 | UDIDI사용종료여부 | BH | Whether the corresponding UDI-DI is in a discontinued state | Supplied Medical Device Information | X | - | - | |
| 61 | 모델일련번호 | BI | Serial number of the model registered with the corresponding UDI-DI | Supplied Medical Device Information | X | - | Product & Code Info | |
| 62 | 공급내역보고자료복합Key | BJ | Composite key composed of Client Code (Column BK) + Supply Details Base Month (Column AZ) + Supply Details Work Serial Number (Column BA) + Supply Details Serial Number (Column BB) | Supply Information | X | - | - | |
| 63 | 거래처 코드 | BK | Number assigned when the supplying company registers the receiving company as a client.<br>* Even if the receiving company is the same, since the number assigned varies depending on the supplying company, it may be displayed as 2 or more client codes. | Supply Information | X | - | Transaction Entity & Identification Info | |
| 64 | 낱개총수량 | BL | Total number of single pieces of the supplied medical device (Supply Quantity (AH) * Total Quantity Within Packaging (AI)) | Supply Information | X | Mandatory | - | Product & Code Info<br>(Since UDI-DI is generated differently per packaging unit, the total supply quantity reflecting the single piece quantity per packaging unit is required) |
| 65 | 업체일련번호(UDIDI 등록업체) | BM | Company serial number of the manufacturing/importing company that first registered the integrated information for the UDI-DI | Supplied Medical Device Information | X | - | System Management Info | |
| 66 | 보고된 UDI-DI의 코드체계 | BN | Code system used to generate the medical device standard code.<br>* Classified into GS1, HIBCC, HIBCC | Supplied Medical Device Information | X | - | - | |
| 67 | 공급한자 업체의 인허가신고번호 | BO | Business license number (Manufacturing/Importing/Sales(Lease)) of the company that supplied the medical device (Columns C, L) | Supplier Information | X | - | Transaction Entity & Identification Info | |
| 68 | 제품명 | BP | Product name of the model registered with the corresponding UDI-DI.<br>* Product name may be null as it is not a mandatory item on the license. | Supplied Medical Device Information | X | - | - | |
| 69 | 품목군 | BQ | Item group classification of the item registered with the corresponding UDI-DI | Supplied Medical Device Information | X | - | - | |
| 70 | 최초접수일자 | BR | Date the supply report data was first uploaded | - | X | - | System Management Info | |
| 71 | 납품업체일련번호 | BS | Company serial number of the company that supplied the medical device | Supplier Information | X | - | System Management Info | |