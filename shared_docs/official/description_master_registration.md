# Medical Device Integrated Information Registration — Data Dictionary (Official Reference)

> **Status:** Authoritative field specification (converted from NIDS/MFDS integrated-registration data dictionary).
> **Edit policy:** PM-maintained official log; agents **read-only**. Do not modify.
> **Companion data:** `shared_data/sample_master_registration_data.xlsx` (sample tier; profile at runtime).
> **Related official doc:** `description_transaction_supply.md` (supply rows link via UDI-DI / item / model serial numbers).

## Purpose of this document

Defines every column in **medical device integrated information registration data** (통합정보): company and device attributes, UDI-DI rules, license-linked fields, and **Core Essential vs Auxiliary Analysis** classifications. Use when interpreting master/registry samples or production registration extracts.

## Relationship to `shared_data/`

| Artifact | Role |
|----------|------|
| `sample_master_registration_data.xlsx` | Executable sample rows for all agents (product/company dimension) |
| This file | Semantic authority for column labels, keys, and input rules — not a fixed runtime schema |

Agents must follow **dynamic ingestion** in `shared_data/DATA_LAYER.md`: discover columns, profile dtypes/nulls, and adapt to drift; treat the table below as reference, not hardcoded code constants.

## Agent usage

| Agent | When to consult |
|-------|-----------------|
| Class 1 — Anomaly | Device class, traceability, reimbursement, license status, UDI keys for graph nodes |
| Class 2 — Forecast | Product hierarchy, discontinuation, packaging quantity per UDI-DI |
| Class 3 — Impact | Policy flags (implantable, orphan, export-use, license cancellation) |

**Hierarchy of truth:** `shared_docs/structured/class_*_spec.md` overrides `official/` for assigned agent analytical work; this file supplies **field definitions** when profiling sample/prod master files.

## Keys and linkage (quick reference)

| Concept | Fields / rule |
|---------|----------------|
| Row identity | Combination of **Medical Device Item Serial** (BK), **Model Serial** (BL), **UDI-DI Serial** (BM) |
| Link from supply reports | Same three serial fields on supply side (see transaction supply dictionary) |
| Top-level categories | **Company Information** (member/registrant) · **Medical Device Information** (license + registration input) |
| UDI-DI uniqueness | One UDI-DI per model name **and** packaging unit (`포장내수량`); same model can yield multiple UDI-DIs |

## Document map

1. **Data item structure** — categories and linkage rules (below).
2. **Data item specification** — full column table (No. 1–93, Excel columns A–CO).

---

## Data item structure and description

### Data Item Structure and Description (Medical Device Integrated Information)

* The integrated information registration data includes data items used for data management in addition to user input data.

* Data is composed of Company Information / Medical Device Information.
* Medical device information supplied from the supply details report data is linked based on [UDI-DI Serial Number / Item Serial Number / Model Serial Number].
    * Company Information: Member information of the Medical Device UDI Tracking Management System.
    * Medical Device Information: Information linked from item license information and input information when creating integrated information registration data.

* Key value distinguishing Medical Device Integrated Information Data = Differentiated by the combination of Medical Device Item Serial Number, Model Serial Number, and UDIDI Serial Number.

---

### Data Item Specification

| No. | Data Item Name | Excel Column | Data Item Description | Data Item Category | Input Value Category | Class 1 (Core Essential / Auxiliary Analysis) | Class 2 (Comments on Changes, etc.) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 번호 | A | Display order when exporting integrated info registration data to Excel | - | - | - | |
| 2 | 통합업체일련번호 | B | Company serial number of the manufacturing/importing company that registered the integrated information | Company Information | - | Core Essential | |
| 3 | 업체명 | C | Name of the company that registered the integrated information | Company Information | License Linked Information | Core Essential | |
| 4 | 업종 | D | Business type of the company that registered the integrated information. <br>* Classified into Manufacturing/Importing. <br>- Manufacturing: Includes [Manufacturing, In Vitro Diagnostic Medical Device Manufacturing, Digital Medical Device Manufacturing]. <br>- Importing: Includes [Importing, In Vitro Diagnostic Medical Device Importing, Digital Medical Device Importing]. | Company Information | License Linked Information | Core Essential | |
| 5 | 업허가번호 | E | Business license number of the company that registered the integrated information | Company Information | License Linked Information | - | |
| 6 | 품목명 | F | Item name of the medical device | Medical Device Information | License Linked Information | Core Essential | |
| 7 | 등급 | G | Grade of the medical device | Medical Device Information | License Linked Information | Core Essential | |
| 8 | 체외진단의료기기여부 | H | Whether the medical device is an 'in vitro diagnostic medical device' | Medical Device Information | License Linked Information | Auxiliary Analysis | * In the case of in vitro diagnostic medical devices, most are not subject to medical device supply details reporting. |
| 9 | 품목분류번호 | I | Item classification number of the medical device | Medical Device Information | License Linked Information | Core Essential | |
| 10 | 품목허가번호 | J | Item license number of the medical device | Medical Device Information | License Linked Information | Core Essential | |
| 11 | 품목허가일자 | K | Date the medical device received item license/report/certification | Medical Device Information | License Linked Information | Core Essential | |
| 12 | 모델명 | L | Model name of the medical device (Mandatory) | Medical Device Information | Mandatory Input (Reflects model name on the license) | Core Essential | |
| 13 | 브랜드명 | M | Product name of the medical device. <br>* As it is not a mandatory item on the license, it may be null. | Medical Device Information | License Linked Information | - | |
| 14 | 통합정보 등록일시 | N | Date and time the medical device integrated information was registered | Medical Device Information | - | Core Essential | |
| 15 | 코드체계 | O | Code system used to generate the medical device UDI-DI. <br>* Can be generated among GS1/HIBCC/ICCBBA systems. | Medical Device Information | Mandatory Input | Auxiliary Analysis | |
| 16 | UDIDI | P | Medical device unique device identifier (UDI-DI) registered for the corresponding model name. <br>* UDI-DI is uniquely generated per medical device model and packaging unit. <br>Example) For model names A and B licensed under No. 12-123, if the internal packaging quantities are 1 and 10 respectively, 2 UDI-DIs are generated. | Medical Device Information | Mandatory Input | Core Essential | |
| 17 | 로트번호 사용여부 | Q | Whether 'Lot Number' information is used in the Production Identifier (UDI-PI) when configuring the medical device standard code (UDI) | Medical Device Information | Mandatory Input | - | |
| 18 | 제품일련번호 사용여부 | R | Whether 'Serial Number' information is used in the Production Identifier (UDI-PI) when configuring the medical device standard code (UDI) | Medical Device Information | Mandatory Input | - | |
| 19 | 제조연월 사용여부 | S | Whether 'Date of Manufacture' information is used in the Production Identifier (UDI-PI) when configuring the medical device standard code (UDI) | Medical Device Information | Mandatory Input | - | |
| 20 | 사용기한 사용여부 | T | Whether 'Expiration Date' information is used in the Production Identifier (UDI-PI) when configuring the medical device standard code (UDI) | Medical Device Information | Mandatory Input | - | |
| 21 | 멸균의료기기 여부 | U | Whether the corresponding product is a "sterilized medical device". <br>* Sterilized medical device: A medical device that undergoes a sterilization process during manufacturing; frequently uses 'Date of Manufacture' and 'Expiration Date' among UDI-PI information. | Medical Device Information | Mandatory Input | Core Essential | * Whether a medical device is sterilized does not affect the medical device supply details reporting target, so it is suggested for auxiliary analysis use. |
| 22 | 포장내수량 | V | Number of single medical device pieces included per corresponding UDI-DI | Medical Device Information | Mandatory Input | - | * UDI-DI is information uniquely generated per model name and product packaging unit; since different UDI-DIs are used even for the same model name depending on the internal packaging quantity, utilization is necessary. |
| 23 | 라텍스 포함여부 | W | Whether the medical device contains latex. <br>* If natural rubber latex is included, direct or indirect contact with the human body may cause allergic reactions, etc. | Medical Device Information | Mandatory Input | - | |
| 24 | 프탈레이트류 포함 여부 | X | Whether the medical device contains phthalates. <br>* Phthalates are related to safety and efficacy issues, such as in IV sets containing them. | Medical Device Information | Conditionally Mandatory. <br>Mandatory when handling IV sets. <br>(Item name: [IV Set, IV Set for Electromotive Drug Infusion Pump, IV Set for Insulin Infusion]) | - | |
| 25 | MRI 안전노출 코드 | Y | If the safety of the medical device in a magnetic resonance (MR) environment is classified and stated on the license (precautions for use, etc.) and attached documents, enter the corresponding details. <br>* Input value: Choose 1 among [Safe / Unsafe / Conditionally Safe / Not Evaluated / Not Applicable]. | Medical Device Information | Mandatory Input | - | |
| 26 | 저장조건 | Z | Text entered during integrated information registration if there are storage conditions for the medical device | Medical Device Information | Optional Input | - | |
| 27 | 유통취급조건 | AA | Text entered during integrated information registration if there are distribution handling conditions for the medical device | Medical Device Information | Optional Input | - | |
| 28 | 버전 | AB | Version information (text) entered during integrated information registration in the case of standalone medical device software | Medical Device Information | Conditionally Mandatory. <br>Mandatory in the case of standalone software medical devices. | - | |
| 29 | 경고금기내용 | AC | Text entered during integrated information registration if there are warning/contraindication contents for the medical device | Medical Device Information | Optional Input | - | |
| 30 | 제품 추가설명 | AD | Text entered during integrated information registration if there is an additional explanation for the medical device | Medical Device Information | Optional Input | - | |
| 31 | 관리자 전화번호 | AE | Phone number of the integrated information management representative of the company registering the integrated information | Medical Device Information | Mandatory Input | - | |
| 32 | 관리자 이메일 | AF | Email of the integrated information management representative of the company registering the integrated information | Medical Device Information | Mandatory Input | - | |
| 33 | 고객센터명 | AG | Name of the customer center, if the company registering the integrated information has one | Medical Device Information | Optional Input | - | |
| 34 | 고객센터연락처 | AH | Contact information of the customer center, if the company registering the integrated information has one | Medical Device Information | Optional Input | - | |
| 35 | 사용전 멸균필요여부 | AI | Whether the product is sterilized prior to use | Medical Device Information | Mandatory Input | - | |
| 36 | 요양급여 대상 여부 | AJ | Whether the product corresponds to a reimbursable treatment material medical device (if it has a benefit or fixed rate code) | Medical Device Information | Mandatory | - | * If a reimbursable medical device is supplied to a medical institution, there is a mandatory supply details reporting obligation for all classes, so utilization is necessary. |
| 37 | 요양급여코드1 | AK | Input of benefit or fixed rate code if the product is a reimbursable treatment material medical device | Medical Device Information | Conditionally Mandatory. <br>Mandatory if the value of column AJ 'Reimbursable Target Status' is Y. | - | |
| 38 | 요양급여코드2 | AL | Input of benefit or fixed rate code if the product is a reimbursable treatment material medical device_2 | Medical Device Information | Conditionally Mandatory. <br>Applicable when there are 2 or more reimbursable codes among cases where the 'Reimbursable Target Status' is Y. | - | |
| 39 | 요양급여코드3 | AM | Input of benefit or fixed rate code if the product is a reimbursable treatment material medical device_3 | Medical Device Information | Conditionally Mandatory. <br>Applicable when there are 2 or more reimbursable codes among cases where the 'Reimbursable Target Status' is Y. | - | |
| 40 | 요양급여코드4 | AN | Input of benefit or fixed rate code if the product is a reimbursable treatment material medical device_4 | Medical Device Information | Conditionally Mandatory. <br>Applicable when there are 2 or more reimbursable codes among cases where the 'Reimbursable Target Status' is Y. | - | |
| 41 | 요양급여코드5 | AO | Input of benefit or fixed rate code if the product is a reimbursable treatment material medical device_5 | Medical Device Information | Conditionally Mandatory. <br>Applicable when there are 2 or more reimbursable codes among cases where the 'Reimbursable Target Status' is Y. | - | |
| 42 | 요양급여코드 미입력 사유 | AP | If the 'Reimbursable Target Status' (Column AJ) is Y, but there is no reimbursable code input value (Columns AK~AO), enter the reason in text | Medical Device Information | Conditionally Mandatory. <br>Applicable when the 'Reimbursable Target Status' is Y but all reimbursable codes (Columns AK~AO) are null. | - | |
| 43 | 물류바코드2 | AQ | An item optionally entered by the company for logistics management, a code composed of GS1/HIBCC/ICCBBA_2 | Medical Device Information | Optional Input | - | |
| 44 | 물류바코드2 포장내수량 | AR | An item optionally entered by the company for logistics management, entering the quantity including the previous stage packaging_2 | Medical Device Information | Optional Input | - | |
| 45 | 물류바코드2 포장차수 | AS | An item optionally entered by the company for logistics management, entered sequentially based on the minimum sales unit packaging_2 | Medical Device Information | Optional Input | - | |
| 46 | 물류바코드3 | AT | An item optionally entered by the company for logistics management, a code composed of GS1/HIBCC/ICCBBA_3 | Medical Device Information | Optional Input | - | |
| 47 | 물류바코드3 포장내수량 | AU | An item optionally entered by the company for logistics management, entering the quantity including the previous stage packaging_3 | Medical Device Information | Optional Input | - | |
| 48 | 물류바코드3 포장차수 | AV | An item optionally entered by the company for logistics management, entered sequentially based on the minimum sales unit packaging_3 | Medical Device Information | Optional Input | - | |
| 49 | 물류바코드4 | AW | An item optionally entered by the company for logistics management, a code composed of GS1/HIBCC/ICCBBA_4 | Medical Device Information | Optional Input | - | |
| 50 | 물류바코드4 포장내수량 | AX | An item optionally entered by the company for logistics management, entering the quantity including the previous stage packaging_4 | Medical Device Information | Optional Input | - | |
| 51 | 물류바코드4 포장차수 | AY | An item optionally entered by the company for logistics management, entered sequentially based on the minimum sales unit packaging_4 | Medical Device Information | Optional Input | - | |
| 52 | 물류바코드5 | AZ | An item optionally entered by the company for logistics management, a code composed of GS1/HIBCC/ICCBBA_5 | Medical Device Information | Optional Input | - | |
| 53 | 물류바코드5 포장내수량 | BA | An item optionally entered by the company for logistics management, entering the quantity including the previous stage packaging_5 | Medical Device Information | Optional Input | - | |
| 54 | 물류바코드5 포장차수 | BB | An item optionally entered by the company for logistics management, entered sequentially based on the minimum sales unit packaging_5 | Medical Device Information | Optional Input | - | |
| 55 | 세트화 여부 | BC | If the value of the 'Whether it is a sterilized medical device prior to use' item (Column BD) is Y during integrated information registration, whether it corresponds to a product configured as a set | Medical Device Information | Conditionally Mandatory. <br>Mandatory if it corresponds to user-sterilized orthopedic supplies. | - | |
| 56 | 사용자 멸균 의료기기 여부 | BD | Whether the product corresponds to 'pre-use sterilized orthopedic supplies' | Medical Device Information | Mandatory Input | - | |
| 57 | 추적관리대상 의료기기 여부 | BE | Whether the product corresponds to a 'traceability management target medical device' | Medical Device Information | License Linked Information | - | |
| 58 | 한벌구성 의료기기 여부 | BF | Whether the product corresponds to a 'set configuration medical device' | Medical Device Information | License Linked Information | Auxiliary Analysis | * Set configuration medical devices are classified as a single item, so separate analysis is unnecessary. |
| 59 | 일회용 의료기기 여부 | BG | Whether the product corresponds to a 'single-use medical device' | Medical Device Information | License Linked Information | Auxiliary Analysis | |
| 60 | 인체이식 의료기기 여부 | BH | Whether the product corresponds to an 'implantable medical device' | Medical Device Information | License Linked Information | Core Essential | |
| 61 | 사용종료 여부 | BI | Whether the registered UDI-DI is processed as 'discontinued' | Medical Device Information | - | - | * In addition to cancellation/withdrawal/transfer/expiration of the item, users can process it as 'discontinued' if the product is no longer manufactured/imported. <br>However, caution is needed for utilization as there are various cases depending on the reason for termination. |
| 62 | 사용종료 사유 | BJ | If the 'Discontinuation Status' (Column BI) of the registered UDI-DI is Y, the text input value for the reason of discontinuation | Medical Device Information | - | - | |
| 63 | 의료기기품목일련번호 | BK | Serial number uniquely assigned per medical device item license. <br>* Can have two or more item serial numbers even with the same UDI-DI. <br>- Example) When using the UDI attached by an overseas manufacturer as-is, there might be two or more companies registering integrated info with the same UDI-DI, but since item licenses differ, they can be distinguished by item serial number. | Medical Device Information | - | Core Essential | |
| 64 | 모델일련번호 | BL | Serial number uniquely assigned per medical device model name | Medical Device Information | - | - | * Utilization is necessary as it corresponds to the key value (Medical Device Item Serial Number, Model Serial Number, UDIDI Serial Number) differentiating medical device integrated information data. |
| 65 | UDIDI일련번호 | BM | Serial number uniquely assigned per UDI-DI | Medical Device Information | - | - | * Utilization is necessary as it corresponds to the key value (Medical Device Item Serial Number, Model Serial Number, UDIDI Serial Number) differentiating medical device integrated information data. |
| 66 | 수정일자 | BN | The date and time the integrated information was last modified | Medical Device Information | - | Core Essential | |
| 67 | 멸균방법1 | BO | If the 'Prior to Use Sterilization Required Status' (Column AI) is Y, the sterilization method selection value_1 | Medical Device Information | Conditionally Mandatory. <br>Mandatory if the 'Prior to Use Sterilization Required Status' is Y. | - | |
| 68 | 멸균방법1_기타 | BP | If the 'Prior to Use Sterilization Required Status' (Column AI) is Y, and 'Other' is selected for sterilization method, the text input value_1 | Medical Device Information | Conditionally Mandatory. <br>Mandatory if the 'Prior to Use Sterilization Required Status' is Y and 'Other' is selected for sterilization method in Column BO. | - | |
| 69 | 멸균방법2 | BQ | If the 'Prior to Use Sterilization Required Status' (Column AI) is Y, the sterilization method selection value_2 | Medical Device Information | Conditionally Mandatory. <br>Mandatory if the 'Prior to Use Sterilization Required Status' is Y. | - | |
| 70 | 멸균방법2_기타 | BR | If the 'Prior to Use Sterilization Required Status' (Column AI) is Y, and 'Other' is selected for sterilization method, the text input value_2 | Medical Device Information | Conditionally Mandatory. <br>Mandatory if the 'Prior to Use Sterilization Required Status' is Y and 'Other' is selected for sterilization method in Column BQ. | - | |
| 71 | 멸균방법3 | BS | If the 'Prior to Use Sterilization Required Status' (Column AI) is Y, the sterilization method selection value_3 | Medical Device Information | Conditionally Mandatory. <br>Mandatory if the 'Prior to Use Sterilization Required Status' is Y. | - | |
| 72 | 멸균방법3_기타 | BT | If the 'Prior to Use Sterilization Required Status' (Column AI) is Y, and 'Other' is selected for sterilization method, the text input value_3 | Medical Device Information | Conditionally Mandatory. <br>Mandatory if the 'Prior to Use Sterilization Required Status' is Y and 'Other' is selected for sterilization method in Column BS. | - | |
| 73 | 멸균방법(','로 구분) | BU | Values of the sterilization method items (Columns BO, BQ, BS) separated by a comma (,) | Medical Device Information | - | - | |
| 74 | 멸균방법_기타(','로 구분) | BV | Values of the other sterilization method input items (Columns BP, BR, BT) separated by a comma (,) | Medical Device Information | - | - | |
| 75 | 요양급여코드(','로 구분) | BW | Values of the reimbursable code items (Columns AK, AL, AM, AN, AO) separated by a comma (,) | Medical Device Information | - | - | |
| 76 | 통합정보 사용중단 일자(YYYYMMDD) | BX | If the 'Discontinuation Status' (Column BI) of the registered UDI-DI is Y, the date processed as discontinued (YYYYMMDD) | Medical Device Information | - | - | |
| 77 | 수출용 여부 | BY | Whether the product is an 'export-use medical device' | Medical Device Information | License Linked Information | - | |
| 78 | 유효기간 만료여부 | BZ | Whether the expiration date on the license item information has expired | Medical Device Information | License Linked Information | - | |
| 79 | 유효기간 | CA | Expiration date on the license item information | Medical Device Information | License Linked Information | Core Essential | |
| 80 | 유효기간 시작일자 | CB | Start date of the expiration period on the license item information (YYYY-MM-DD) | Medical Device Information | License Linked Information | - | |
| 81 | 유효기간 종료일자 | CC | End date of the expiration period on the license item information (YYYY-MM-DD) | Medical Device Information | License Linked Information | - | |
| 82 | 갱신신청 시작일자 | CD | Start date when application for license renewal is possible (YYYYMMDD) | Medical Device Information | License Linked Information | - | |
| 83 | 갱신신청 종료일자 | CE | End date when application for license renewal is possible (YYYYMMDD) | Medical Device Information | License Linked Information | - | |
| 84 | 갱신신청 상태 | CF | Electronic civil service processing status if a license renewal application has been made | Medical Device Information | - | - | |
| 85 | 취소/취하 | CG | Status of the item, classified into Cancelled / Withdrawn / Transferred / Expired (Expiration Date). <br>* If the current item license is cancelled/withdrawn, the UDI-DI is automatically processed as discontinued. | Medical Device Information | License Linked Information | - | * Utilization is necessary when needed by including the current status of the item license (Normal or Cancelled / Withdrawn / Transferred / Expired). |
| 86 | 희소의료기기 여부 | CH | Whether the item registered with integrated information corresponds to an 'orphan medical device' | Medical Device Information | License Linked Information | - | |
| 87 | 코드중복등록여부 | CI | Y if 2 or more of the registered UDI-DIs exist among the total UDI-DIs | Medical Device Information | - | - | |
| 88 | 코드중복등록사유 | CJ | If the 'Code Duplicate Registration Status' (Column CI) is Y, text input value for the reason for duplicate registration of the code | Medical Device Information | - | - | |
| 89 | 품목허가번호 취소/취하 일자 | CK | If there is a value in the 'Cancelled/Withdrawn' item (Column CG), the date of cancellation / withdrawal / transfer / expiration (expiration date) | Medical Device Information | License Linked Information | - | * Utilization is necessary when needed by including the current status of the item license (Normal or Cancelled / Withdrawn / Transferred / Expired). |
| 90 | 통합정보 최초 등록일시 | CL | Date and time the integrated information was first registered | Company Information | - | - | |
| 91 | 제조원국가 | CM | Country of the manufacturer in the case of imported products | Medical Device Information | License Linked Information | - | |
| 92 | 업종 | CN | Business type of the company that registered the integrated information. <br>* Classified into [Manufacturing, In Vitro Diagnostic Medical Device Manufacturing, Digital Medical Device Manufacturing, Importing, In Vitro Diagnostic Medical Device Importing, Digital Medical Device Importing]. | Company Information | License Linked Information | Core Essential | * As a detailed classification of the business type in Column D, data utilization based on Column D classification is necessary during analysis. |
| 93 | 품목군 | CO | Item group of the corresponding medical device | Medical Device Information | License Linked Information | Core Essential |
