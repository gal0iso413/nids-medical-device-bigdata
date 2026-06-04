# Class 1 — Anomaly Detection Specification

> **Status:** Active — proposal and kickoff bodies populated; PM may refine thresholds below.
> **Authority:** Supersedes `official/` interpretations for Agent 1 analytical mandate when in conflict.

## Scope

- Unsupervised distribution anomaly tracking
- Graph-relationship analysis when structure is inferable

## PM refinements (optional)

- Target entities and segmentation dimensions
- Anomaly definitions and escalation thresholds
- Required outputs for Phase 1 EDA and later phases
- Integration points with Class 2 / Class 3 (read-only awareness; no cross-spec implementation)

## Body

### Initial Document (제안서)

#### 1. Problem Definition & Operational Objectives
- **Business Pain Points:** The presence of indirect supply ("간납" - indirect delivery) where a sales company bypasses direct delivery to medical institutions and routes through third-party purchasing/distribution agencies. This causes price opacity, unclear distribution liability, and safety management blind spots.
- **Operational Objectives:** Objectively and quantitatively detect abnormal distribution structures (such as suspected indirect supply, abnormal brokerage patterns, and abnormal price margins) using data-driven network analysis and composite anomaly scoring.

#### 2. Input Data & Feature Dimensions
- **Data Sources:** - Internal: UDI Registration Info, Supply Details Report (공급내역보고).
  - External/Public: Reimbursement Claims (급여청구), Procurement Delivery (조달납품), Company Info.
- **Specific Feature Variables:**
  - `udi_di` [의료기기 고유식별자]: Primary key for tracking distribution paths of the same product.
  - `manufacturer_license` [제조업 허가번호]: Used to verify supplier legitimacy.
  - `manufacturer_name` [제조업자 명칭]: Confirms supply chain consistency.
  - `single_use_yn` [일회용 여부]: Detects anomalies in reuse or re-distribution.
  - `traceable_yn` [추적관리대상 여부]: Used to flag high-risk items for intensive monitoring.
  - `device_class` [의료기기 등급 (1~4)]: Determines the risk weight multiplier.
  - `reimburse_yn` [요양급여 대상 여부]: Compares distribution consistency against reimbursement claims.

#### 3. Algorithmic Modeling & Analytical Tech Track
- **Network Construction:** Converts supply report data into a Directed Graph $G = (V, E)$, where $V$ represents supply actor nodes (Manufacturer, Sales Company, Medical Institution) and $E$ represents supply transaction edges mapped by `udi_di` with weight $w(e)$ being supply quantity or transaction amount.
- **Heuristics & Algorithms:**
  - **Path Depth Index (PDI):** $PDI_{udi} = max_{p \in P(udi)}|path(p)| \ge 3 \Rightarrow$ Suspected indirect supply.
  - **Betweenness Centrality (BC) for Hub Detection:** $BC(v) = \sum_{s \ne v \ne t} \frac{\sigma_{st}(v)}{\sigma_{st}}$. Flags entities in the Top 5% as suspicious abnormal brokers.
  - **Herfindahl-Hirschman Index (HHI) for Transaction Concentration:** $HHI_{item} = \sum_{i=1}^{n} s_{i}^{2}, s_{i} = \frac{Q_{i}}{\Sigma Q}$. An HHI > 0.25 (single company exceeding 50% share) indicates supply monopoly anomaly.
  - **Price Margin Z-Score:** $Z_{price} = \frac{P_{stage_{k}} - \overline{P}_{stage}}{\sigma_{stage}} > 2.0 \Rightarrow$ Abnormal pricing detected.
  - **Rule-based Anomaly Flags:** Discrepancy between transaction volume and business scale, and supply of unregistered items despite having a license.
- **Composite Anomaly Score:** - $AnomalyScore = w_1 I[PDI \ge 3] + w_2 I[BC > P95] + w_3 I[HHI > 0.25] + w_4 \cdot I[Z_{price} > 2]$.
  - Weights ($w_i$) are dynamically adjusted based on `device_class` and `traceable_yn`.

#### 4. System Interface & Output Deliverables
- **Outputs:** An overall Anomaly Score quantitatively classifying transactions.
- **Visuals:** Network visualizer mapping normal paths ($PDI \le 2$), suspected indirect supply routes ($PDI \ge 3$), and highlighting abnormal entities ($BC$ Top 5%).

### Main Document (착수보고서)

#### 1. Problem Definition & Operational Objectives
- **Business Pain Points:** The medical device market is growing rapidly, but unfair transactions within the supply chain increase national healthcare burdens. Indirect suppliers (간납사) exploit their monopolistic positions derived from "special relationships" (특수관계) with medical institutions to charge ungrounded commissions ranging from 3% to 30%. Furthermore, they force consignment (가납/수탁) practices without issuing tax invoices, delaying payments for up to 6 months and transferring inventory risks to suppliers.
- **Operational Objectives:** Preemptively detect abnormal distribution structures—such as funneling bottlenecks, special-relation monopolies, multi-stage detours, long-term consignment lag, and excessive margins—by employing multi-dimensional network analysis and AI anomaly detection to prevent health insurance financial leaks.

#### 2. Input Data & Feature Dimensions
- **Nodes (Supply Chain Entities):**
  - `Supplier` [공급자]
  - `Receiver` [공급받은자]
  - `Company Serial Number` [공급한자/받은자 업체일련번호]
  - `Medical Institution Code` [요양기관기호(의료기관)]
  - `Business Registration Number` [사업자등록번호]
  - `Business Type` [업종 / 공급받은자업종]
  - `Location Code` [소재지 시도코드]
- **Objects (Devices):**
  - `UDI` [표준코드(UDI)]
  - `Item Name` [품목명]
  - `Item Group` [품목군]
  - `Device Class` [등급]
  - `Traceability Target` [추적관리대상]
  - `Single-Use Status` [일회용여부]
- **Edges (Transactions):**
  - `Supply Amount` [공급금액]
  - `Supply Qty` [공급수량]
  - `Unit Price` [공급단가]
  - `Supply Date` [공급일자]
  - `First Receipt Date` [최초접수일자]
  - `Lot Number` [로트번호]
  - `Serial Number` [일련번호]
- **Engineered Features:**
  - `Path Depth Index (PDI)` [유통경로 깊이]: Total edge count from the initial manufacturer to the final medical institution.
  - `Robust Z-score / MAD` [단가 이상치]: Statistical deviation of the unit price markup compared to the median market margin of the same item group.
  - `Herfindahl-Hirschman Index (HHI)` [거래 집중도]: Squared sum of supply proportions from individual suppliers to a specific medical institution.
  - `Time-lag` [가납(수탁) 의심 지연일수]: Difference between the physical supply date and the administrative receipt date.

#### 3. Algorithmic Modeling & Analytical Tech Track
- **Phase 1: Robust Statistical Filter (1st Pass):**
  - Uses Median Absolute Deviation (MAD) and Robust Z-score instead of the mean to prevent margin averages from being skewed by extreme profiteers.
  - Applies differential PDI thresholds based on the device's risk class (Class 1 vs. Class 4) to avoid false positives for complex but legitimate supply chains.
- **Phase 2: Graph ML (2nd Pass):**
  - **Isolation Forest:** Automatically isolates anomalous transactions in a multi-dimensional space utilizing price, quantity, and transaction frequency.
  - **Graph Representation (GraphSAGE, Node2Vec):** Vectorizes the entire distribution network structure to detect closed, special-relationship clusters and evasive multi-stage detours.
- **Output:** Combines indicators to produce a continuous Anomaly Score ranging from 0 to 100 rather than a binary classification.

#### 4. System Interface & Output Deliverables
- **Scoring Dashboard:** An interactive dashboard displaying individual transactions and entities with a 0~100 Anomaly Score.
- **Explainable AI (XAI) Report:** Text-based rationale specifying exact factors (e.g., 40% due to HHI monopoly, 60% due to margin anomaly).
- **Network Visualizer:** A graphical map exposing funneling bottlenecks and multi-stage detour paths directed toward specific hospitals.

---