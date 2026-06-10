# Methods Research — MCDM and 2D Portfolio Mapping for Device Impact Prioritization

> **Agent:** class_3_impact_evaluation  
> **Date:** June 7, 2026  
> **Research question:** Review Multi-Criteria Decision-Making (MCDM) approaches (Weighted Sum vs TOPSIS/AHP) and 2D portfolio mapping methodologies (Clinical Severity vs Supply Risk) for prioritizing medical devices under Korean healthcare-dependency constraints.

---

## 1. Problem framing

The Korean medical device supply chain is highly vulnerable to international shocks, with tertiary hospitals experiencing upwards of an 87.5% import dependency for critical, life-saving devices. Historically, the National Institute of Medical Device Safety Information (NIDS) and the Ministry of Food and Drug Safety (MFDS) have relied on a simplistic, 1-dimensional volume-based ranking system to prioritize devices. This system conflates generic, high-volume domestic consumables (e.g., IV lines, syringes) with highly specialized, imported, and irreplaceable implantable devices (e.g., graft stents) that may have low transaction counts but carry catastrophic clinical consequences during a disruption.

For NIDS Class 3 (Impact Evaluation), our mandate is to orthogonalize supply chain evaluation into two distinct axes: **Clinical Impact (Severity)** and **Supply Risk (Likelihood of Disruption)**, mapping devices into a 2-dimensional portfolio (Kraljic-style matrix) to support strategic stockpiling, R&D localization, and vendor diversification. Because these prioritization decisions directly impact hospital operations, national budget allocations, and public health policies, the underlying MCDM and portfolio mapping framework must be highly robust, mathematically consistent, and exceptionally interpretable for non-technical government stakeholders.

---

## 2. Method candidates

We compare three Multi-Criteria Decision-Making (MCDM) approaches and one Unsupervised Clustering technique for device impact prioritization and portfolio mapping.

### 2.1 Weighted Sum Model (WSM) with Heuristic Correction

- **Idea:** Formulate a transparent, linear scoring model where clinical and supply risk metrics are normalized to a $[0, 1]$ scale and linearly combined using preset weights.
  $$Score_i = \sum_{k=1}^{K} W_k \cdot S_{ik}$$
  Following the initial proposal, base scores are dynamically adjusted using heuristic multipliers for exceptional risk classes:
  $$Adjusted~Score_i = Score_i \cdot (1 + \sum \alpha_j \cdot I[\text{Anomaly Flag}_j])$$
  where $\alpha_j$ represents upward multipliers for features like implantable status, traceability, and imported single-use items.
- **Data requirements:** Normalized continuous and categorical indicators (e.g., HHI concentration, unique hospital coverage, device class).
- **Pros:**
  1. **Unmatched Interpretability:** Extremely intuitive for policymakers. The contribution of each sub-metric to the final score is additive and transparent.
  2. **Proportional Sensitivity Analysis:** Enables interactive slider-based simulation, allowing stakeholders to dynamically adjust weights ($W_k$) and immediately observe rank shifts.
  3. **Low Sample Sensitivity:** Highly stable on small datasets; does not suffer from convergence or training failures.
- **Cons:**
  1. **Linear Compensability:** High performance in one category can completely mask a critical failure in another (e.g., a device with massive supply volume but zero domestic substitutes might receive an average score).
  2. **Subjective Weighting:** Relies on administrative consensus for weight parameters rather than empirical optimization.
- **Interpretability:** **Exceptional.** Perfect for public administrative hearings and legal audits (e.g., "This device scored 84/100 because it has a high supplier concentration (HHI) contributing 25 points, broad clinical coverage contributing 20 points, and a Class 4 regulatory multiplier").

### 2.2 TOPSIS (Similarity to Ideal Solution)

- **Idea:** Rank medical devices based on their geometric distance to a hypothetical "Positive Ideal Solution" ($A^+$, representing the maximum risk across all indicators) and a "Negative Ideal Solution" ($A^-$, representing the minimum risk). The relative closeness coefficient ($C_i$) is calculated as:
  $$C_i = \frac{d_i^-}{d_i^+ + d_i^-}$$
  where $d_i^+$ and $d_i^-$ are the Euclidean distances to the ideal best and worst. Items with $C_i$ closest to $1.0$ represent the highest priority.
- **Data requirements:** Multi-criteria decision matrix containing normalized continuous metrics.
- **Pros:**
  1. **Captures Non-Linear Trade-Offs:** Does not assume simple linear compensation. An alternative must be close to the worst case on at least some dimensions to rank high.
  2. **No Linear Scaling Bias:** Avoids the distortive effects of standard linear min-max scaling across highly skewed distributions.
- **Cons:**
  1. **Rank Reversal Pitfall:** Adding or removing a device from the evaluation pool can alter the positions of the "ideal" vectors, causing the relative ranks of existing items to reverse.
  2. **Poor Stakeholder Intuition:** Explaining a relative closeness coefficient based on multi-dimensional Euclidean distance is highly abstract and difficult to defend legally during vendor appeals.
- **Interpretability:** **Moderate.** The ranking is easy to present, but the exact mathematical justification for a specific item's position is a black box to non-statisticians.

### 2.3 Analytic Hierarchy Process (AHP) for Criteria Weighting

- **Idea:** Deconstruct the prioritization problem into a hierarchical structure (Goal $\rightarrow$ Axes $\rightarrow$ Criteria). Decision-makers construct a series of pairwise comparison matrices using Saaty's 1-to-9 scale to establish criteria priorities. The principal eigenvector of the comparison matrix yields the weight vector, and the consistency of the judgments is verified using the Consistency Ratio ($CR < 0.10$).
- **Data requirements:** Subjective pairwise comparison matrices from clinical and logistics experts.
- **Pros:**
  1. **Mathematically Rigorous Weighting:** Replaces arbitrary weight assignments with a structured, consistent, and validated consensus mechanism.
  2. **Defends Against Cognitive Bias:** The Consistency Ratio identifies and flags contradictory or irrational expert judgments.
- **Cons:**
  1. **Poor Scalability ($O(n^2)$):** Performing pairwise comparisons of alternatives scales quadratically with the number of devices. It is computationally and cognitively impossible to perform AHP on thousands of individual `UDI-DI` models.
- **Interpretability:** **High (for Criteria Weighting only).** Stakeholders highly appreciate the structured, collaborative process of setting weights, even if they cannot use AHP to score the individual items.

### 2.4 Gaussian Mixture Models (GMM) for 2D Portfolio Clustering

- **Idea:** Instead of dividing the clinical impact (Y-axis) and supply risk (X-axis) into arbitrary quadrants using rigid 50th/75th percentile splits, fit a Gaussian Mixture Model (GMM) to the 2D coordinate space. GMM treats each portfolio quadrant as a soft-clustering probability distribution, capturing ellipsoidal clusters that reflect natural density variations in the transaction network.
- **Data requirements:** Calculated 2D coordinate pairs ($Supply~Risk_i, Clinical~Impact_i$) for all active devices.
- **Pros:**
  1. **Identifies Empirical Personas:** Discovers natural clusters (e.g., "High-Volume Domestic Commodities," "Sole-Source Foreign Monopolies") directly from data.
  2. **Handles Uncertainty:** Provides soft membership probabilities, highlighting borderline items that sit between strategic and bottleneck categories.
- **Cons:**
  1. **Unstable on Low Sample Sizes:** Fitting a GMM with multiple mixtures on a sample of 38 unique products will overfit or fail to find stable clusters.
  2. **Dynamic Boundaries:** Cluster boundaries shift as new transaction data arrives, making year-over-year policy comparisons difficult.
- **Interpretability:** **Moderate.** The resulting clusters make intuitive sense as "personas," but the underlying probabilistic clustering boundaries are harder to defend than fixed administrative thresholds.

---

## 3. Fit to current sample data

We evaluate the feasibility of executing these methods on the current **Sample Tier** data:

- **Robust Clinical Coverage Breadth:** The `sample_transaction_supply_data.xlsx` covers transactions supplied directly to **210 unique medical institutions** (hospital codes `요양기관기호(의료기관)`). This provides a high-fidelity, continuous measure of *Clinical Coverage Breadth* on the clinical impact axis.
- **Supplier Concentration Metrics (X-Axis):** The transaction logs allow direct, continuous calculations of market concentration. On the sample data, we calculated a Quantity-based **HHI of 1,428.97** (moderate concentration) with Becton Dickinson Korea holding a **33.76% quantity share** (Top 3 joint share is **50.77%**). These concentration metrics represent a highly robust, non-subjective input for the Supply Risk (X-Axis) calculation.
- **Substitutability Proxy:** In the Master registry, we successfully engineered a *Substitutability Proxy* based on the ratio of unique manufacturers to models per `품목명` (Item Name). For example, `담관용스텐트` has 217 models but only 1 manufacturer (extremely low substitutability, representing high systemic risk), while `수액세트` has a 1:1 manufacturer-to-model ratio (high substitutability).
- **Key Disjointness & Feature Missingness (0.00% Overlap):** 
  - *Mitigation:* Due to the absolute disjointness between the sample Master and Supply files, we cannot directly join master-specific covariates (like clinical `등급` and `일회용 의료기기 여부`) to supply transaction rows. 
  - *Proxying:* For Phase 1-2, we must build our 2D coordinates primarily from the Supply log. Supply-side transactions are all Class 4 high-risk implantable items, providing a baseline Clinical Severity. To test the clinical impact variance, we must use the continuous hospital coverage count (`요양기관기호(의료기관)`) as our primary Y-axis driver.
- **Supply Classification Null Drift:** The `품목군` (Item Group) column in the Supply sheet has a **61.73% null rate**. 
  - *Mitigation:* Any pipeline must dynamically map and fill missing item groups from the Master registry based on standardized UDI-DI lookups, rather than relying on the noisy, unpopulated Supply-side column.
- **Zero-Price Pricing Filter:** 44.7% of transaction rows have unit prices of 0.0 KRW (B2B transfers).
  - *Mitigation:* For market value and concentration calculations, we must filter transactions to keep only those with `공급형태` = `"의료기관에 공급"` (where zero-pricing is only 3.7%) to avoid massive statistical dilution.

---

## 4. Execution sketch

```
                      [ Clean Supply Transaction Logs ]
                                      │
                     ┌────────────────┴────────────────┐
                     ▼                                 ▼
           [ Supply Risk (X-Axis) ]          [ Clinical Impact (Y-Axis) ]
           - HHI Concentration Index         - Baseline Device Class (Class 4)
           - Top 3 Quantity Share            - Unique Hospital Coverage Count
           - Import Proxy (Supplier type)    - Inventory Expiry Horizon (Supply logs)
                     │                                 │
                     ▼                                 ▼
           [ Normalization (MinMax) ]        [ Normalization (MinMax) ]
                     │                                 │
                     └────────────────┬────────────────┘
                                      ▼
                        [ Linear Multi-Criteria Fusion ]
                                      │
                                      ▼
                    [ 2D Orthogonal Portfolio Coordinate ]
                                      │
                                      ▼
                     [ 4-Quadrant Kraljic Matrix Mapping ]
                     - Quadrant 1: Strategic (High Risk, High Impact)
                     - Quadrant 2: Bottleneck (High Risk, Low Impact)
                     - Quadrant 3: Routine (Low Risk, Low Impact)
                     - Quadrant 4: Leverage (Low Risk, High Impact)
```

### Step 1: Normalization & Axis Calculation
Apply Min-Max Normalization to continuous criteria to ensure equal scale $[0, 1]$ before applying weights:
$$X_{\text{norm}} = \frac{X - X_{\text{min}}}{X_{\text{max}} - X_{\text{min}}}$$

Calculate the coordinate axes for each unique device model (`UDI-DI`):
1. **Supply Risk Score (X-Axis):**
   $$RiskScore = W_{\text{HHI}} \cdot HHI_{\text{norm}} + W_{\text{Share}} \cdot Top3Share_{\text{norm}} + W_{\text{Import}} \cdot I[\text{Importer}]$$
2. **Clinical Impact Score (Y-Axis):**
   $$ImpactScore = W_{\text{Hosp}} \cdot HospCount_{\text{norm}} + W_{\text{Class}} \cdot Class_{\text{norm}} + W_{\text{Expiry}} \cdot ExpiryHorizon_{\text{norm}}$$

### Step 2: 2D Quadrant Boundary Assignment
Map items into the four portfolio quadrants using the median ($P_{50}$) or 75th percentile ($P_{75}$) of the calculated coordinates as the orthogonal boundaries.
* **Strategic (Q1):** $Risk \ge P_{50}$ AND $Impact \ge P_{50}$
* **Bottleneck (Q2):** $Risk \ge P_{50}$ AND $Impact < P_{50}$
* **Routine (Q3):** $Risk < P_{50}$ AND $Impact < P_{50}$
* **Leverage (Q4):** $Risk < P_{50}$ AND $Impact \ge P_{50}$

---

## 5. Evaluation plan

- **Baselines:**
  - **Baseline A (1-Dimensional Volume):** Prioritization ranking based solely on total transaction quantity (`공급수량`).
  - **Baseline B (Static Administrative Rules):** Flat classification where any Class 4 implantable item is automatically labeled as "High Priority" regardless of supply concentration or hospital coverage.
- **Evaluation Metrics:**
  - **Rank Consistency Index (RCI):** Measure the percentage of rank reversals that occur when criteria weights are adjusted by $\pm 10\%$. A robust MCDM system should exhibit an RCI $> 0.90$ (indicating stable ranking).
  - **Cluster Separation (Silhouette Width):** For unsupervised clustering (K-Means/GMM), evaluate the separation between the strategic and routine clusters.
  - **Policy Target Accuracy:** Quantify the percentage of imported, single-source clinical items (true risks) that are successfully captured in the Strategic (Q1) quadrant versus the baseline models.
- **Leakage & Methodological Risks:**
  - **Concentration Index Lookahead Bias:** Market concentration (HHI) must be calculated over fixed, retrospective temporal windows (e.g., trailing 6 months) relative to the evaluation date. Calculating HHI using future transaction data will leak future supply consolidations back in time, leading to unrealistic prioritization signals.
  - **Small-Sample Clustering Overfitting:** Due to having only 38 unique `UDI-DI` codes in the sample tier, K-Means and GMM are highly prone to overfitting on localized noise. We must constrain the maximum number of clusters ($k$) to exactly 4 (matching the Kraljic quadrants) and use a simple Euclidean distance metric.

---

## 6. References

1. **Wesley Partners NIDS Class 3 Specification (`class_3_evaluation_spec.md`):** Defines the mathematical formulation for impact scoring, evaluation criteria, and 2D portfolio mapping rules. [Verified Authority].
2. **Saaty, T. L. (1980).** *The Analytic Hierarchy Process: Planning, Priority Setting, Resource Allocation*. McGraw-Hill. [Verified Classic AHP Foundation - ISBN: 978-0070543713].
3. **Hwang, C. L., & Yoon, K. (1981).** *Multiple Attribute Decision Making: Methods and Applications*. Springer-Verlag. [Verified Classic TOPSIS Reference - ISBN: 978-3540105589].
4. **Kraljic, P. (1983).** "Purchasing must become supply management." *Harvard Business Review*, 61(5), 109-117. [Verified Classic Portfolio Mapping Reference].

---

## 7. Recommendation and open questions

### Core Recommendation

For the NIDS Class 3 deployment, we strongly recommend a **Structured Hybrid MCDM-Portfolio Framework** that prioritizes stakeholder transparency and administrative defensibility:

1. **Criteria Weighting (AHP):** Utilize AHP solely at the administrative level to build consensus and establish the baseline weights ($W_k$) among clinical, regulatory, and logistics experts. This provides a mathematically verified, bias-resistant foundation for weight selection.
2. **Scoring and Normalization (Weighted Sum Model):** Implement a **Weighted Sum Model (WSM)** with Min-Max normalization as the core scoring engine. Reject TOPSIS for public-facing deployments due to its susceptibility to rank reversal and low algebraic transparency.
3. **Visualization (4-Quadrant Kraljic Matrix):** Plot the WSM scores on an interactive, orthogonal 2D scatter plot (Clinical Severity vs Supply Risk) where quadrant boundaries are defined by administrative percentiles ($P_{50}$ or $P_{75}$).
4. **Validation (GMM Clustering):** Use Gaussian Mixture Models (GMM) strictly as a secondary, backend validation tool to confirm that the boundaries of the 4 quadrants align with natural, data-driven clusters (personas) in the transaction space.

### Key PM Decision Points & Open Questions

1. **Defining the Quadrant Split Thresholds:** Should we split the 2D portfolio quadrants using the median ($P_{50}$, which guarantees a balanced distribution of items across all quadrants) or the 75th percentile ($P_{75}$, which strictly isolates only the top 6.25% of absolute high-risk, high-impact items in the Strategic quadrant)? We recommend using $P_{75}$ for the Strategic quadrant to prevent strategic stockpiles from being diluted by moderately critical items.
2. **Handling Sample Key Disjointness:** Given the 0.00% join overlap in the sample tier, should we utilize simulated master-to-supply lookups to test clinical covariates (like detailed device class and single-use status), or should we rely purely on transaction-level metrics (hospital coverage and supply quantity) for Phase 1-2 testing?
3. **Managing Supply-Side Null Drift:** How should the pipeline handle the 61.73% missingness in the Supply file's `품목군` (Item Group) column? We recommend implementing an automated fallback lookup that standardizes the UDI-DI and pulls the correct `품목군` directly from the Master registration sheet.
