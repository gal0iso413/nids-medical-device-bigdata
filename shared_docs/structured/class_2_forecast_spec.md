# Class 2 — Supply Forecast Specification

> **Status:** Active — proposal and kickoff bodies populated; PM may refine SLAs below.
> **Authority:** Supersedes `official/` interpretations for Agent 2 analytical mandate when in conflict.

## Scope

- Time-series and rolling-window signals
- Early-warning framing; survival-style analysis when applicable
- What-If simulation (post-approval)

## PM refinements (optional)

- Forecast horizon and alert SLAs
- Temporal grain and aggregation rules
- Scenario parameters for What-If modules

## Body

### Initial Document (제안서)

#### 1. Problem Definition & Operational Objectives
- **Business Pain Points:** Unpredictable medical device supply disruptions caused by decreased production/imports, end-of-use filings, or delayed registrations.
- **Operational Objectives:** Structure supply disruption indicators into time-series features, apply weights to calculate a Risk Score, and categorize disruption risk into High, Medium, and Low for proactive supply management. 

#### 2. Input Data & Feature Dimensions
- **Data Sources:** - Internal: UDI Registration Info, Supply Details Report, End-of-Use & Modification History.
  - External: Reimbursement Claims, Import/Production Performance, Company Info.
- **Specific Feature Variables:**
  - `udi_di` [의료기기 고유식별자]: Key for generating item-level supply time-series.
  - `overseas_manufacturer` [해외제조원 정보]: Calculates import dependency.
  - `manage_expiry` [사용기한 관리 여부]: Models inventory exhaustion risk.
  - `approval_date` [허가일자]: Determines the product life-cycle variable.
  - `device_class` [의료기기 등급]: Determines risk weight multiplier.
  - `implantable_yn` [인체이식형 여부]: Weight applied for supply disruption impact.
  - `contract_manufacturer` [위탁제조자]: Indicator of supply chain vulnerability.
  - `reimburse_code` [요양급여 코드]: Key for linking National Health Insurance data.

#### 3. Algorithmic Modeling & Analytical Tech Track
- **Time-Series Feature Extraction:**
  - Monthly supply time-series: $Q_t (t=1,...,T)$.
  - YoY Change Rate: $\Delta Q_t = \frac{(Q_t - Q_{\{t-12\}})}{Q_{\{t-12\}}}$.
  - Moving Average Deviation: $Dev_t = Q_t - MA(Q,6)$.
  - Surge in End-of-Use Registration: $\Delta EoL_t$.
  - Delay Days: Days un-registered after modification event.
- **Risk Score Aggregation:** - $Risk~Score = \sum(W_i \times S_i)$. 
  - Indicator weights ($W_i$): Sudden surge in end-of-use (0.25), Production drop > 30% (0.25), Import drop > threshold (0.20), Increase in license withdrawal/cancellations (0.20), Registration delay > 10 days (0.10).
- **Survival Analysis (Cox Proportional Hazard Model & Kaplan-Meier):**
  - Defines 'Supply Disruption' as the target Event ($d_j$).
  - Hazard Function: $h(t|X) = h_0(t) \cdot exp(\sum_{j=1}^{p} \beta_j X_j)$.
  - Kaplan-Meier Estimate: $\hat{S}(d_k) = \prod_{j=1}^{k}(\frac{r_j - q_j}{r_j})$.
  - Covariates ($X_j$): Import dependency, Single manufacturer status, Production decrease rate, End-of-use surge, Years since approval, Device class.

#### 4. System Interface & Output Deliverables
- **Outputs:** Classification into High Risk ($\ge 0.7$), Medium Risk (0.4~0.7), and Low Risk ($< 0.4$).
- **Visuals:** Kaplan-Meier survival curves explicitly plotting the "probability of future supply disruption" over time (months).

---

### Main Document (착수보고서)

#### 1. Problem Definition & Operational Objectives
- **Business Pain Points:** Medical device supply disruptions occur unpredictably due to production/import decreases, end-of-use filings, and registration delays, lacking a proactive management framework.
- **Operational Objectives:** Detect and predict supply disruption probability by structurally engineering time-series supply data, classifying disruption risks into High, Medium, and Low tiers to secure supply stability.

#### 2. Input Data & Feature Dimensions
- **Core Entity Variables:**
  - `UDI-DI` [의료기기 고유식별자]
  - `Overseas Manufacturer` [해외제조원 정보]
  - `Expiry Management` [사용기한 관리 여부]
  - `Approval Date` [허가일자]
  - `Device Class` [등급]
  - `Implantable Status` [인체이식형 여부]
  - `Contract Manufacturer` [위탁제조자]
  - `Reimbursement Code` [요양급여 코드]
  - `Traceable Device` [추적관리대상 의료기기 여부]
  - `Orphan Device` [희소의료기기 여부]
  - `Export Only` [수출용 여부]
  - `Business Type` [업종]
- **Time-Series Engineered Features:**
  - `Monthly Supply Qty` [$Q_t$]
  - `YoY Change Rate` [$\Delta Q_t$]
  - `6/12 Month Moving Average` [$MA6_t, MA12_t$]
  - `Moving Average Deviation` [$Dev_t$]
  - `Recent 6M / Past 12M Ratio` [$Decline_t$]
  - `Customer Diversity` [$n_{cust_t}$]
  - `Silent Days` [$days_{silent}$]

#### 3. Algorithmic Modeling & Analytical Tech Track
- **Risk Score Aggregation (Binary Flags):**
  - Supply Volume Drop ($Decline_t \le 0.5$): Weight 0.25.
  - Long-term Silence ($days_{silent} \ge 180$): Weight 0.25.
  - Customer Churn ($\Delta n_{Cust} \le -2$): Weight 0.20.
  - Aging Item (Approval Age > 10 years): Weight 0.20.
  - High-Risk Item (Class 4 OR Implantable OR Traceable): Weight 0.10.
- **Survival Analysis (Kaplan-Meier & Cox Proportional Hazard):**
  - **Event Definition:** Supply disruption ($d_j$) is defined as having no transactions for 180 days with cumulative transactions $\ge N$. Right-censoring is applied for active items.
  - **Kaplan-Meier Estimate:** $\hat{S}(d_k) = \prod_{j=1}^{k} \frac{r_j - q_j}{r_j}$ estimates the non-parametric probability of maintaining supply over time.
  - **Cox Hazard Function:** $h(t|X) = h_0(t) \cdot \exp(\sum_{j=1}^{p} \beta_j X_j)$ quantifies risk factors (covariates).
  - **Covariates ($X_j$):** Business type (Import Dependency), Approval date (U-shaped non-linear risk), Device class (Class 4 risk), Implantable status, Traceability, Orphan status, and Customer diversity.

#### 4. System Interface & Output Deliverables
- **Risk Categorization:** Output classification into High ($\ge 0.7$), Medium (0.4~0.7), and Low ($< 0.4$) risk tiers.
- **Survival Curve Visualizer:** Explicit Kaplan-Meier plotting of the "future probability of supply disruption" distributed over elapsed time.

---