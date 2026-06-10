# Methods Research — Medical Device Supply Disruption Early Warning

> **Agent:** class_2_supply_forecast  
> **Date:** June 7, 2026  
> **Research question:** Review methods for medical device supply disruption early warning — comparing Heuristics-Based Weighted Risk Scores against Survival Analysis (Cox Proportional Hazards and Kaplan-Meier Estimator) on sparse, monthly medical device transaction series.

---

## 1. Problem framing

The stability of the medical device supply chain is a critical national security and public health concern. Medical device supply disruptions—caused by raw material shortages, overseas manufacturing bottlenecks, regulatory delays, or sudden end-of-use (EoL) filings—frequently catch healthcare providers off guard. Proactive supply management requires an early-warning system capable of detecting supply disruptions *before* clinical inventory is exhausted.

For NIDS Class 2 (Supply Forecast), our operational mandate is to engineer monthly transaction series into predictive risk signals and classify unique device models (`UDI-DI`) into high, medium, and low-risk tiers. Under the **Sample Tier** constraints (24 months of contiguous monthly data, 38 unique `UDI-DI` codes, and absolute physical disjointness between the Master registration and Transaction logs), traditional forecasting models like SARIMA or deep-learning LSTMs fail due to extreme data sparsity, short historical horizons, and a lack of documented supply-disruption events. We must evaluate whether **Heuristics-Based Weighted Risk Scores** or **Survival Analysis (Cox / Kaplan-Meier)** provides a more robust, statistically sound, and legally defensible alerting framework.

---

## 2. Method candidates

We compare four candidate methodologies for early warning of medical device supply disruptions under severe sparsity and low historical event rates.

### 2.1 Heuristics-Based Weighted Risk Scores (Rule-Based Fusion)

- **Idea:** Formulate a composite Risk Score $RS_t \in [0, 1]$ as a weighted linear combination of binary anomaly flags calculated over rolling windows:
  $$RS_t = \sum_{i=1}^{n} W_i \cdot S_{i,t}$$
  where $S_{i,t} \in \{0, 1\}$ represents individual indicators (e.g., volume drops, prolonged silence, customer churn, product aging, and high-risk regulatory classes), and $W_i$ represents preset expert-derived weights. High risk is flagged when $RS_t \ge 0.7$, Medium risk at $0.4 \le RS_t < 0.7$, and Low risk at $RS_t < 0.4$.
- **Data requirements:** Aggregated monthly transaction quantities ($Q_t$), customer counts ($n_{cust}$), and product characteristics (e.g., import status, device class).
- **Pros:** 
  1. **Extreme Data Tolerance:** Operates perfectly on sparse series with zero historical disruption events; does not require statistical model fitting or optimization.
  2. **Highly Robust:** Immune to overfitting, convergence failures, or small-sample statistical bias.
  3. **Direct Operational Alignment:** Directly mirrors the regulatory requirements outlined in the Class 2 initial proposal and main document.
- **Cons:**
  1. **Subjective Weighting:** Weights ($W_i$) are defined *a priori* by administrative experts rather than learned from historical empirical distributions.
  2. **Static Alert Horizon:** Does not model the continuous "time-to-disruption" or provide a probability curve of future supply availability.
- **Interpretability:** **Exceptional.** Easily explainable to clinical or administrative stakeholders (e.g., "This stent is High Risk (0.80) because it is a Class 4 implantable device (0.10), its supply volume dropped by >50% (0.25), and it has been silent for over 180 days (0.25)").

### 2.2 Kaplan-Meier Estimator (Non-parametric Survival)

- **Idea:** Estimate the non-parametric probability of an item maintaining continuous supply over time. The "event" (Supply Disruption) is defined as $days_{silent} \ge 180$ with cumulative historical volume $\ge N$. Active products are right-censored at the end of the observation window. The survival probability at time $d_k$ (expressed as elapsed months since the product's first transaction or last known stable period) is:
  $$\hat{S}(d_k) = \prod_{j=1}^{k} \frac{r_j - q_j}{r_j}$$
  where $r_j$ is the number of active ("at risk") device models, and $q_j$ is the number of models experiencing a disruption event at step $j$.
- **Data requirements:** A structured survival matrix containing the elapsed time-to-event (or censoring) and a binary event indicator ($Event \in \{0, 1\}$).
- **Pros:**
  1. **Rigorously Handles Censoring:** Naturally accounts for products that remain active at the end of the 24-month sample period without treating them as "safe" or "failed."
  2. **Dynamic Visual Output:** Yields the required "Survival Curve" showing the probability of future supply availability over time.
- **Cons:**
  1. **No Covariate Support:** KM is purely univariate; it cannot incorporate product-level risk factors (e.g., import dependency, customer diversity) to adjust individual curves.
  2. **Severe Sparsity Bias:** With only 38 unique `UDI-DI` codes in the sample tier and few expected events, the survival curve will be blocky, unstable, and statistically weak.
- **Interpretability:** **High (Visual).** Administrative users can easily interpret the curve: "The probability of this category maintaining stable supply for the next 6 months is 82%."

### 2.3 Cox Proportional Hazards Model (Semi-parametric Survival)

- **Idea:** Model the hazard rate of supply disruption for an individual device model as a function of multiple underlying risk covariates:
  $$h(t|X) = h_0(t) \cdot \exp(\sum_{j=1}^{p} \beta_j X_j)$$
  where $h_0(t)$ is the baseline hazard and $X_j$ represents covariates (such as import dependency proxy, customer diversity, product age, and device class). The coefficients $\beta_j$ are estimated via partial likelihood maximization.
- **Data requirements:** Survival matrix (time, event) mapped to a vector of static and dynamic covariates.
- **Pros:**
  1. **Quantifiable Risk Factors:** Statistically evaluates the relative hazard of different covariates (e.g., "Imported devices exhibit a 2.3x higher risk of sudden disruption").
  2. **Dynamic Multi-factor Adjustment:** Adjusts survival curves for individual products based on their unique risk profile.
- **Cons:**
  1. **Failure to Converge on Low Events:** Standard Cox models suffer from extreme numerical instability and over-fitting when the number of events per covariate (EPV) is less than 10. In our sample tier, with very few true disruptions, a multi-covariate Cox model will fail to converge.
  2. **Proportional Hazards Assumption:** Assumes the effect of covariates is constant over time, which may not hold for supply chains where import shocks are highly seasonal or episodic.
- **Interpretability:** **Moderate.** Coefficients represent Hazard Ratios (HR), which require statistical literacy to explain during audits or administrative appeals.

### 2.4 Poisson / Negative Binomial Zero-Inflated Regression (Sparse Count Models)

- **Idea:** Instead of modeling "time-to-event," model the monthly transaction count $Y_{i,t}$ directly as a random variable. Since transaction series are sparse and heavily zero-inflated (due to low ordering frequencies), model the series using a Zero-Inflated Poisson (ZIP) or Zero-Inflated Negative Binomial (ZINB) regression. A sudden shift in the estimated probability of the "always-zero" state serves as the early warning.
- **Data requirements:** Panel data of monthly transaction counts per `UDI-DI` over time.
- **Pros:**
  1. **Direct Series Modeling:** Uses the full continuous monthly sequence rather than collapsing it into a single "time-to-event" data point.
  2. **Distinguishes Zero-Inflation Types:** Statistically separates structural zeroes (true disruption) from sampling zeroes (regular sparse ordering pattern).
- **Cons:**
  1. **Complex Formulation:** Significantly harder to implement and validate on a small sample of 38 products over 24 months.
  2. **Low Audit Defensibility:** Results are highly abstract (e.g., changes in log-likelihood space) and lack direct intuitive appeal for non-technical policymakers.
- **Interpretability:** **Low.** Translating zero-inflated model coefficients into administrative alerts is highly complex.

---

## 3. Fit to current sample data

We evaluate the feasibility of executing these methods on the current **Sample Tier** data:

- **Contiguous Time-Series (Jan 2024 - Dec 2025):** The `sample_transaction_supply_data.xlsx` provides exactly 24 continuous months of data with 12,558 transaction rows. This allows precise calculation of rolling windows (such as $Decline_t$ based on a 6-month/12-month ratio, $MA6_t$, and $MA12_t$).
- **Severe Key Disjointness (0.00% Overlap):** The registration master (510 rows) and transaction supply logs have zero key overlap.
  - *Mitigation:* We cannot directly join master-specific covariates (like detailed `품목허가일자` or `등급` distributions) to the transaction series. However, the Supply file's `등급` is 100% populated with Class 4 and `인체이식형 의료기기여부` is 100% "예" (implantable). 
  - *Proxying:* Since the master-file `제조원국가` is null, we can build a highly effective binary **Import Dependency Proxy** directly from the Supply file by checking if the supplier's business type (`업종`) is `"수입업"` (importer, representing 27.1% of transactions, including Becton Dickinson Korea).
- **High-Fidelity Expiry Data:** Although the Master file's expiration usage field has a 48.63% null rate, the Supply file's actual expiration date (`사용기한`) is **99.97% populated** in YYMMDD format. This enables us to calculate an **Inventory Exhaustion Horizon** (Months to Expiry = Expiration Date - Transaction Date) directly from supply logs, serving as a powerful survival covariate or standalone warning indicator.
- **Zero-Price B2B Bias:** 44.7% of Supply records have `공급단가` = 0.0.
  - *Mitigation:* These zero-price records represent physical movements (B2B transfers). For **Survival Analysis**, we must preserve these records because the presence of any transaction (even at 0.0 KRW) indicates active supply, meaning the product is not disrupted. However, for pricing-based risk calculations or value-weighted volume aggregation, we must restrict analysis to records with `공급형태` = `"의료기관에 공급"` (where zero-pricing is only 3.7%).

---

## 4. Execution sketch

```
                          [ Raw Supply Transactions ]
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
           [ Physical Flow Graph ]            [ Financial Flow Graph ]
           Keep all rows (incl. 0.0)         Filter: Hospital Supply only
                      │                                 │
                      ▼                                 ▼
         [ Define Survival Matrices ]         [ Calculate Rolling Windows ]
         - Active window: 24 months           - Decline_t = MA6 / MA12
         - Event: days_silent >= 180          - Customer Churn: Delta n_Cust
         - Expiry Horizon: Months to Expiry    - Import Proxy: Supplier Type == Importer
                      │                                 │
                      ▼                                 ▼
         [ Non-Parametric Survival ]          [ Heuristic Risk Score Engine ]
           Kaplan-Meier Estimator              Weighted Linear Fusion (0.0 - 1.0)
                      │                                 │
                      └────────────────┬────────────────┘
                                       ▼
                         [ Hybrid Alert Dashboard ]
                         - Alert Tier: High/Med/Low
                         - Probability of Survival over Time
```

### Step 1: Preprocessing & Event Definition
1. Parse `공급일자` as datetime: `pd.to_datetime(df['공급일자'].astype(str), format='%Y%m%d')`.
2. Map supplier's `업종` == `"수입업"` to binary `is_imported`.
3. Compute continuous inactive gaps: for each `UDI-DI`, calculate the number of days since the last transaction on any given date.
4. Construct the survival dataset at the product (`UDI-DI`) level:
   - **Duration ($T$):** Number of months from the first observed transaction to the first day of a 180-day silent period, or to the end of the 24-month study window (December 31, 2025) if active.
   - **Event ($E$):** `1` if the product entered a 180-day silent period during the window; `0` if right-censored (active).

### Step 2: Running Kaplan-Meier
Using the `lifelines` Python library, fit KM curves to estimate baseline category survival:
```python
from lifelines import KaplanMeierFitter
kmf = KaplanMeierFitter()
kmf.fit(durations=df_survival['T'], event_observed=df_survival['E'])
# Yields baseline probability curve of maintaining supply over elapsed months
```

### Step 3: Heuristics-Based Scoring
In parallel, calculate the rolling monthly risk score for active items:
1. **$S_{Decline}$:** `1` if $Decline_t \le 0.5$, else `0` (Weight: 0.25).
2. **$S_{Silence}$:** `1` if $days_{silent} \ge 180$, else `0` (Weight: 0.25).
3. **$S_{Churn}$:** `1` if $n_{cust, t} - n_{cust, t-6} \le -2$, else `0` (Weight: 0.20).
4. **$S_{Aging}$:** `1` if product age > 10 years, else `0` (Weight: 0.20). (Can be proxyed or simulated until production joins are available).
5. **$S_{HighRisk}$:** `1` (since all Supply samples are Class 4 implantable, Weight: 0.10).
6. Calculate composite: $Risk~Score_t = 0.25 \cdot S_{Decline} + 0.25 \cdot S_{Silence} + 0.20 \cdot S_{Churn} + 0.20 \cdot S_{Aging} + 0.10 \cdot S_{HighRisk}$.

---

## 5. Evaluation plan

- **Baselines:** 
  - **Baseline A:** Static volume drop trigger (alert if $Q_t$ drops by >50% YoY).
  - **Baseline B:** Simple historical average depletion model (projecting past 3 months' average volume against the median expiry date in supply logs).
- **Evaluation Metrics:**
  - **Receiver Operating Characteristic Area Under Curve (ROC-AUC):** Evaluate how well the 0–1.0 continuous Risk Score predicts an actual supply disruption (defined as a subsequent 180-day silence) at a 3-month and 6-month prediction horizon.
  - **Concordance Index (C-index):** For survival models, evaluate the rank-order agreement between predicted hazard rates and actual times-to-disruption.
  - **Alert Density & Administrative Burden:** Quantify the percentage of products classified into the "High Risk" tier. A healthy early-warning system should flag no more than 3% to 5% of products concurrently to prevent administrative alert fatigue.
- **Leakage & Methodological Risks:**
  - **Lookahead Bias:** All rolling window features (e.g., 6-month moving averages or customer counts) must be calculated strictly using historical data relative to time step $t$ ($t_{history} \le t$). Calculating a moving average using data from $t+1$ to $t+6$ will leak the disruption event back in time, falsely inflating model accuracy.
  - **Bootstrap Validation (Few-Event Mitigation):** Because the 24-month sample tier contains very few true disruption events, standard train/test splits are highly unstable. We must use **bootstrap resampling** (resampling unique `UDI-DI` clusters with replacement 1,000 times) to generate robust confidence intervals for our metric scores.

---

## 6. References

1. **Wesley Partners NIDS Class 2 Specification (`class_2_forecast_spec.md`):** Outlines the mathematical formulas for Risk Score fusion and survival analysis framework. [Verified Authority].
2. **Cox, D. R. (1972).** "Regression Models and Life-Tables." *Journal of the Royal Statistical Society: Series B (Methodological)*, 34(2), 187-200. [Verified Classic Cox Foundation - DOI: 10.1111/j.2517-6161.1972.tb00899.x].
3. **Kaplan, E. L., & Meier, P. (1958).** "Nonparametric Estimation from Incomplete Observations." *Journal of the American Statistical Association*, 53(282), 457-481. [Verified Classic KM Foundation - DOI: 10.1080/01621459.1958.10501452].
4. **Harrell, F. E., et al. (1982).** "Evaluating the predictive accuracy of survival analysis models in the presence of censoring." *Biometrics*, 316-320. [Verified C-index reference - DOI: 10.2307/2530245].

---

## 7. Recommendation and open questions

### Core Recommendation

For the initial operational rollout, we strongly recommend a **Hybrid Staged Warning System** that fuses the immediate robustness of the Heuristic Risk Score with the long-term temporal insights of Survival Analysis:

1. **Stage 1 (Operational Alerting - Heuristics):** Use the Heuristics-Based Weighted Risk Score as the primary, legally defensible, and highly explainable alert mechanism. Its lack of reliance on fit parameters makes it highly reliable for sparse, low-event sample data.
2. **Stage 2 (Macro-Level Risk Profiling - Kaplan-Meier):** Use Kaplan-Meier survival curves to estimate baseline survival probabilities *by product category* (e.g., stents vs catheters) or *by import status* (imported vs domestic), rather than trying to fit individual product-level curves.
3. **Stage 3 (Inference - Cox):** Postpone fitting multi-covariate Cox Proportional Hazard models until the production tier is loaded and at least 30–50 true supply disruption events are observed. Trying to fit Cox on the current sample tier will result in extreme overfitting and statistical noise.

### Key PM Decision Points & Open Questions

1. **Defining the Disruption Threshold ($N$):** The spec defines disruption as "no transactions for 180 days with cumulative transactions $\ge N$." What is the threshold $N$ for our sample tier? If $N$ is set too low, we will flag low-volume items as "disrupted" simply because their natural purchasing cycle is sparse. We recommend setting $N$ dynamically based on the median inter-transaction interval of the product.
2. **Handling Sample Disjointness:** Since the master registry has 0.00% overlap with the supply transactions in the sample tier, how should we represent the "product age" covariate in Stage 1 testing? Should we mock this covariate (e.g., assign random ages between 1 and 15 years to Taewoong/GS Medical products), or rely entirely on transaction-derived features (like customer diversity and silent days) for Phase 1-2 testing?
3. **Expanding the Expiry Date Metric:** The Supply file has a 99.97% fill rate for the actual expiration date (`사용기한`). Can we incorporate a new binary flag in our Heuristics Score, such as "Exhaustion Risk" (flagged if the median remaining shelf-life of active stock is $< 6$ months), to proactively warn of inventory expiration?
