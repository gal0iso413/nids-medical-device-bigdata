# Medical Device Distribution Big Data — Program Specification (Official Reference)

> **Status:** Authoritative program/RFP specification (NIDS stakeholder source).
> **Edit policy:** PM-maintained official log; agents **read-only**. Do not modify.
> **Document reference:** Request for Proposal (RFP), Jan 28, 2026.
> **Related official docs:** `description_master_registration.md`, `description_transaction_supply.md` (operational field dictionaries).

## Purpose of this document

Provides **program-level** context for the NIDS medical-device distribution big-data optimization initiative: legal mandates, deliverables, data-entity taxonomy, contract timeline, and phased UDI/supply reporting rules. Use for strategic alignment when PM directs; pair with field dictionaries for column-level work.

## Relationship to agent work and data

| Layer | Location | Role |
|-------|----------|------|
| Program scope & deliverables | This file | Mission, tasks, milestones, regulatory phase-in |
| Column semantics | `description_*` in this folder | Master and supply field definitions |
| Agent execution rules | `shared_docs/structured/class_*_spec.md` | Per-agent scope (supreme for that agent on conflict) |
| Sample/prod files | `shared_data/` | Runtime inputs — profile dynamically per `DATA_LAYER.md` |

## Agent usage

| Agent | When to consult |
|-------|-----------------|
| All (when PM directs) | Contract phases, deliverable names, 300M+ transaction scale, MFDS federation scope |
| Class 1 — Anomaly | §2.3 anomalous distribution model; implantable / class reporting windows |
| Class 2 — Forecast | §2.3 supply disruption model; supply reporting milestone dates |
| Class 3 — Impact | §2.3 policy support model; public/regulator/industry channel mapping |

**Hierarchy of truth:** `shared_data/DATA_LAYER.md` for ingestion; structured agent specs govern analytical implementation; this file is **immutable stakeholder reference** for program intent and architecture labels (`UDI_MASTER_01`, `TX_METRICS_04`, etc.).

## Stakeholder metadata

| Field | Value |
|-------|--------|
| **Originating organization** | National Institute of Medical Device Safety Information (NIDS), Integrated Information Data Team (Digital Product Evaluation Center) |
| **Project authority** | Kim Pureum (Team Leader, +82-02-860-4442) |
| **Platform** | Medical Device UDI Tracking Management System — external portal: `emedi.mfds.go.kr/udi` |

## Document map

| Section | Contents |
|---------|----------|
| §1 | Mission, scale, legal mandates |
| §2 | Technical scope, deliverables, three analytic model types + pilot |
| §3 | Legacy systems and data-ingestion entity matrix |
| §4 | 120-day schedule, budget, procurement |
| §5 | UDI registration and supply reporting phase-in by device class |

---

## 1. Mission and Context
### 1.1 Public Health & Safety Mission
* **Systemic Oversight:** Enable end-to-end trace management and lifecycle tracking from manufacturing/importation through distribution to the end consumer/medical facility.
* **Regulatory Mechanism:** Utilize the Unique Device Identification (UDI) Tracking Management System to collect comprehensive registration and supply history data, enforcing transparency and regulatory compliance across the industry.
* **Public/Policy Utility:** Establish an actionable intelligence framework to dynamically support healthcare policy formulation, research & development, industry trend modeling, and predictive public health safety measures.

### 1.2 Scale and Regulatory Foundation
* **Data Volume:** Over 300 million cumulative transactions processed and archived as of 2025.
* **Legal Mandates:** * *Medical Devices Act Decree Article 10-6 Paragraph 2 Clause 1:* Statutory authority for the aggregation, processing, utilization, and distribution of medical device logistics data.
    * *Medical Devices Act Article 31-2:* Mandatory reporting of supply and distribution metrics.
    * *Medical Devices Act Article 31-3:* Mandatory generation and registration of Unique Device Identification metadata.
    * *Medical Devices Act Article 31-4 & Decree Article 10-6:* Designation and delegation of the Medical Device Integrated Information Center operations to NIDS.

---

## 2. Technical Scope & Core Tasks

### 2.1 Technical Auditing & Roadmapping
* **Diagnostic Audit:** Evaluate the current state of data ingestion, structural integrity, and distribution analysis workflows. Conduct structured interviews with core database administrators and business process owners.
* **Strategic Deliverable:** **[Data Analysis Current State & Improvement Strategy Report]** * Must incorporate formal user interview matrix.
    * Must deliver a mid-to-long term platform evolution strategy and explicit implementation roadmap.

### 2.2 Multi-Agency Data Federation
* **Cross-Border Integration:** Architect protocols to ingest and merge heterogeneous datasets from external ministries and public authorities.
* **Target Datasets:** Core focus on Ministry of Food and Drug Safety (MFDS) structural layers—specifically production volumes, importation values, and product recall logs.
* **Strategic Deliverable:** **[Data Federation Expansion Strategy Report]** * Must identify explicit, combinable data fields across entities.
    * Must construct contextual integration scenarios and practical utility frameworks.

### 2.3 Predictive Modeling & Analytics Framework
* **Stakeholder Distribution Channel Mapping:** Design distinct information delivery and data utilization frameworks for three primary target groups: Government/Regulators, Industry/Enterprises, and the Public.
* **Target Analytics Models:** Conceptualize and define at least three separate analytical models addressing public health risks and anomalies:
    1.  *Supply Chain Disruption Model:* Predict shortages and supply vulnerabilities using early-warning indicator signals.
    2.  *Anomalous Distribution Logic Model:* Identify structural anomalies, illegal rerouting, or irregular pricing matrices.
    3.  *Policy Support Model:* Contextual data mining based on internal, public, and private sector open data inputs.
* **Strategic Deliverable:** **[Medical Device Distribution Data Utilization Report]** * Must contain formal technical design specs for the proposed analytical models and consecutive launch roadmaps.
    * Requires integration of multi-disciplinary expert advisory panels and working working groups to validate data veracity.

### 2.4 Pilot Analytical Engineering
* **Implementation Target:** Programmatically implement, optimize, and evaluate exactly one high-priority analytical model from the discovered candidates.
* **Execution Parameters:** Perform technical database architecture setup, system development, data engineering pipelines, and final analysis execution. Output must focus on concrete actionable insights and rich interactive visualizations.
* **Strategic Deliverable:** **[Data Analytical Model Pilot Implementation Report]** * Must assess real-world business process compatibility and regulatory policy viability.
    * Must define specific scaling parameters and technical adjustments required for future full-scale enterprise deployment.

---

## 3. Data Architecture and Schema Constraints

### 3.1 Legacy and Current Platform Landscape
* *Medical Device Integrated Information System:* Launched July 2019.
* *Next-Generation Medical Device Integrated Information System:* Consolidated February 2023; currently operating under the unified **Medical Device UDI Tracking Management System** (External Portal URL: `emedi.mfds.go.kr/udi`).

### 3.2 Data Ingestion & Structural Matrix

| Core Entity Category | Data Attribute Identifier | Specific Field Names & Contents |
| :--- | :--- | :--- |
| **Medical Device Master Metadata** | `UDI_MASTER_01` | Unique Device Identification (UDI) Standard Codes |
| | `PROD_INFO_02` | Generic & Commercial Product Nomenclature, Product License/Permit Index Numbers |
| | `CORP_INFO_03` | Manufacturer Identity Records, Importer Corporate Profiles, Operator License Identifiers |
| | `MISC_DATA_04` | Auxiliary system inputs and operational fields |
| **Supply & Distribution Transactions** | `SUPPLIER_01` | Source Entity Metadata, Corporate Registration ID, Entity Classification |
| | `RECIPIENT_02` | Destination Entity Metadata, Medical Institution Identifiers, Sub-distributor Profiles |
| | `ITEM_DATA_03` | Transacted Product Standard Identifiers, Production Batch Numbers |
| | `TX_METRICS_04` | Quantitative Transaction Volume, Absolute Supply Date, Financial Settlement Amount/Unit Price |

---

## 4. Operational Schedule & Execution Model

### 4.1 Chronological Milestone Tracking
* **Total Contract Duration:** Maximum 120 Days from formal contract finalization.
* **Operational Execution Phasing (`M` = Contract Commencement Month):**
    * **Month M:** Procurement Finalization & Contract Signing $\rightarrow$ System Ingestion & Integrated Project Plan Submission (**Inception Briefing / 착수보고**).
    * **Month M+1 to M+2:** Core Diagnostic Auditing $\rightarrow$ Multi-Agency Data Federation Field Engineering $\rightarrow$ Analytical Model Scoping.
    * **Month M+2 to M+3:** Middle Review Milestone (**Midterm Briefing / 중간보고**) $\rightarrow$ Pilot Analytical Model Engineering & Validation.
    * **Month M+4:** System Visualization Output Optimization $\rightarrow$ Handover Strategy Planning $\rightarrow$ Final Performance Review (**Final Briefing / 최종보고**) $\rightarrow$ Comprehensive Artifact Handover.

### 4.2 Procurement Constraints
* **Budget Ceiling:** 50,000,000 KRW (VAT Inclusive).
* **Procurement Format:** Limited Competitive Tendering / Negotiation-based Contract / Accelerated Emergency Notification.
* **Evaluation Balance Weight:** Technical Capabilities Score (90%) + Price Competitiveness Score (10%). Large conglomerate participation is structurally restricted.

---

## 5. Regulatory Phase-In Rules (Historical Context Matrix)

Analytical logic models must account for tiered data availability dates based on historical statutory implementation schedules:

### UDI Master Metadata Registration Milestones
* **Class 4 Devices:** Mandatory from July 1, 2019
* **Class 3 Devices:** Mandatory from July 1, 2020
* **Class 2 Devices:** Mandatory from July 1, 2021
* **Class 1 Devices:** Mandatory from July 1, 2022

### Supply Chain Logistics Reporting Milestones
* **Class 4 Devices:** Mandatory from July 1, 2020
* **Class 3 Devices:** Mandatory from July 1, 2021
* **Class 2 Devices:** Mandatory from July 1, 2022
* **Class 1 Devices:** Mandatory from July 1, 2023
* *Special Condition (Implantable Medical Devices):* Complete distribution track-and-trace monitoring enforced exclusively for Class 3 and Class 4 variations.
* *Special Condition (Reimbursement/Therapeutic Materials):* Restricts reporting boundary explicitly to transaction sequences terminating directly at a Medical Institution (must include precise unit pricing metrics).
* *Reporting Windows:* Logistics data files must be committed to the database no later than the final calendar day of the month succeeding the absolute transaction month.