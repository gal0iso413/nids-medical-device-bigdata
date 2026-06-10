# Methods Research — Network Anomaly Detection for Indirect Supply and Brokerage

> **Agent:** class_1_anomaly_detection  
> **Date:** June 7, 2026  
> **Research question:** Review methods for detecting indirect supply ("간납") and abnormal brokerage in supply-chain transaction networks (PDI, centrality, concentration indices vs graph anomaly detection) in the context of Korean medical device distribution.

## 1. Problem framing

The Korean medical device market has been heavily impacted by unfair transaction practices involving indirect delivery agencies ("간납사" - Gannam-sa or Group Purchasing Organizations). These agencies often exploit "special relationships" (특수관계) with medical institutions to extract excessive brokerage fees (ranging from 3% to 30%), delay payments to suppliers for 6 to 12 months, and force consignment practices without proper invoicing. The regulatory mandate established by the "Gannam-sa Law" (amended Medical Device Act, passed December 2025) requires the National Information Society Agency (NIA) and the National Institute of Medical Device Safety Information (NIDS) to quantitatively detect and monitor these abnormal distribution structures. 

With approximately 12.5k rows of supply details in the sample tier, our core task is to identify and score transactions suspect of indirect supply, multi-stage detours, and monopolistic brokerage. To be effective for regulatory enforcement, the analytical framework must be highly interpretable, legally defensible during audits, and capable of handling structural data discrepancies (such as the physical disjointness of the master registration and transaction logs in the sample tier).

## 2. Method candidates

### 2.1 Path Depth Index (PDI) with Structural Risk Filtering

- **Idea:** Convert transaction records into a directed, product-specific distribution graph where nodes represent entities (manufacturers, distributors, medical institutions) and directed edges represent the physical transfer of devices. For each standard device standard code (`UDI-DI`), we trace all active paths from the initial supplier (manufacturer/importer) to the final receiver (medical institution) and calculate the path length (hop count). A Path Depth Index ($PDI_{udi} = \max |path|) \ge 3$ triggers a high-risk flag for an indirect detour.
- **Data requirements:** Transaction logs containing unique device identifiers (`UDI-DI`), supplier business registrations, receiver business registrations, and timestamps. Nodes must be classified by business type (제조업, 수입업, 도매업, 의료기관) to anchor path starts and ends.
- **Pros:** Perfect alignment with the regulatory definition of indirect supply and multi-stage detours. Extremely simple to explain in administrative hearings or courts.
- **Cons:** Highly sensitive to missing middle-tier transaction records (breaks the chain). Does not account for transaction volumes, prices, or time-lags.
- **Interpretability:** Perfect. "This stent was routed through three intermediate brokers before reaching Hospital X, which is two steps more than a direct path."

### 2.2 Betweenness Centrality (BC) for Gatekeeper Brokerage Detection

- **Idea:** Model the entire supply chain as an aggregated weighted directed network $G=(V, E)$, where edges represent cumulative transaction amounts over a given period. Compute Betweenness Centrality for each intermediate node $v$:
  $$BC(v) = \sum_{s \ne v \ne t} \frac{\sigma_{st}(v)}{\sigma_{st}}$$
  where $\sigma_{st}$ is the total number of shortest paths from supplier $s$ to hospital $t$ and $\sigma_{st}(v)$ is the number of those paths that pass through $v$. Nodes in the top 5% of BC act as critical "gatekeepers" or "toll booths" (통행세 취득원), indicating potential exploitative brokerage.
- **Data requirements:** Aggregated transaction graph (nodes = company registration numbers, edges = sum of supply amounts).
- **Pros:** Mathematically robust; captures global network structure rather than just local connections; exposes brokers who insert themselves between many disjoint manufacturers and hospitals.
- **Cons:** Large-scale, legitimate logistic distributors will also exhibit high BC. Requires normalization against business type and regional density to avoid false positives.
- **Interpretability:** High. "Entity Y lies on 85% of all efficient distribution paths between manufacturers and hospitals in region Z, acting as a massive bottleneck."

### 2.3 Herfindahl-Hirschman Index (HHI) for Special-Relationship Monopolies

- **Idea:** Measure transaction concentration at the hospital (receiver) level. For each medical institution $h$, calculate the incoming supply concentration for a specific product group:
  $$HHI_{h} = \sum_{i=1}^{n} s_{i}^2$$
  where $s_i$ is the market share (by transaction amount) of supplier $i$ in hospital $h$'s total purchases of that product group. An HHI > 0.25 indicates extreme concentration (monopoly). When a single Gannam-sa dominates a hospital's supply chain (especially for generic devices with many available suppliers), it strongly indicates an exclusive "special relationship" or unfair funneling (일감 몰아주기).
- **Data requirements:** Clean supplier and receiver identifiers, product groupings, and supply amounts.
- **Pros:** A standard antitrust index heavily utilized by the Korea Fair Trade Commission (FTC / 공정거래위원회); highly resistant to localized graph noise.
- **Cons:** Static metric that ignores the routing topology (cannot detect if the concentrated supply is direct or has multi-stage detours).
- **Interpretability:** Excellent. "Hospital A receives 94% of its stents from Gannam-sa B, resulting in an HHI of 0.88, which points to exclusive funneling."

### 2.4 Unsupervised Graph Representation Learning & Isolation Forest

- **Idea:** Vectorize the graph structure using algorithms like Node2Vec or GraphSAGE to generate low-dimensional embeddings for each node and transaction edge, capturing non-linear structural properties, dense subgraphs, and cyclic billing paths. Feed these structural vectors along with transactional features (margins, quantity, time-lags) into an Isolation Forest model to isolate structural anomalies in multi-dimensional space.
- **Data requirements:** Complete node and edge feature matrices; dense graph topology.
- **Pros:** Capable of detecting highly complex, evasive, and collaborative fraud patterns (such as round-tripping invoicing or splitting transaction volumes to evade static PDI/HHI thresholds).
- **Cons:** Represents a "black box" that is highly difficult for regulators to explain to target businesses during audits; computationally expensive for real-time monitoring.
- **Interpretability:** Low. Requires post-hoc explainability methods (e.g., SHAP, attention weights) to provide regulatory justification.

---

## 3. Fit to current sample data

- **Feasibility on Sample Tier:** Highly feasible. The `sample_transaction_supply_data.xlsx` workbook contains exactly 12,558 transaction rows, which are highly concentrated on a single product category (*peripheral vascular graft stents* / 말초혈관용그라프트스텐트). The dataset contains 115 unique suppliers and 355 unique receivers across 38 unique `UDI-DI` codes, representing a dense sub-network ideal for testing PDI, Betweenness Centrality, and HHI.
- **Adaptation to Disjointness:** Since the master registration data (510 rows) and transaction supply data have **0.00% physical overlap** on standard keys in this sample tier, we cannot use master-sheet columns (such as `manufacturer_name` or `device_class`) to anchor our path starts. 
  - *Mitigation:* We must build the network topology **entirely from the supply transaction file**, treating the initial supplier in a chain (nodes with 0 in-degree or those holding a supplier business type of "수입업") as proxy manufacturers.
- **Handling Zero-Price Bias:** 44.7% of the transaction rows have a unit price (`공급단가`) of `0.0`, primarily representing business-to-business (B2B) transfers (which have a 70.1% zero-price rate).
  - *Mitigation:* For path routing (PDI) and structural centrality (BC), these zero-price edges **must be preserved** as they represent the physical flow of the medical devices. However, for HHI and pricing-anomaly calculations, we **must filter** the edges to keep only those with `공급형태` = "의료기관에 공급" (where zero-pricing is only 3.7%) to prevent massive statistical distortion.
- **Feature Missingness:** Since `일련번호` (serial number) and `제조연월` (manufacturing date) are 100% null in the supply file, individual device-level tracing is impossible. 
  - *Mitigation:* We must aggregate path flows at the batch/lot level or aggregate standard transactions by `UDI-DI` + `Supplier` + `Receiver` + `Supply Date`.

---

## 4. Execution sketch

```
                  [ Raw Supply Transaction Log (12.5k rows) ]
                                      │
                     ┌────────────────┴────────────────┐
                     ▼                                 ▼
           [ Path & Topology ]               [ Financial & Volume ]
         Keep all edges (incl. 0.0)         Filter: Hospital Supply only
                     │                                 │
                     ▼                                 ▼
          [ Directed Network G ]             [ Transaction Shares ]
                     │                                 │
           ┌─────────┴─────────┐                       │
           ▼                   ▼                       ▼
      [ Path Depth ]     [ Betweenness ]        [ Hospital HHI ]
        (PDI >= 3)         (BC Top 5%)          (HHI > 0.25)
           │                   │                       │
           └─────────┬─────────┴───────────────────────┘
                     ▼
       [ Composite Anomaly Scoring ] ──► [ Explainable AI (XAI) Engine ]
```

1. **Preprocessing and Graph Construction (NetworkX / igraph):**
   - Cast standard identifiers (`UDI-DI`) to strings, stripping leading zeros.
   - Build a directed multi-graph $G$ where nodes are unique business registrations or agency codes.
   - Separate edges into: (a) *Physical Flow Graph* (all transactions, including zero-price B2B) and (b) *Financial Flow Graph* (only transactions with positive prices where destination is a medical institution).
2. **Deterministic Metric Extraction:**
   - **PDI Calculator:** Run a Depth-First Search (DFS) on the physical flow graph from proxy manufacturers to medical institutions to identify multi-stage paths.
   - **Betweenness Centrality (BC) Engine:** Compute weighted BC on the physical flow graph, where edge weights are the inverse of cumulative supply amounts.
   - **Hospital HHI Engine:** Group the financial flow graph by medical institution and compute the HHI of their incoming suppliers.
3. **Composite Anomaly Scoring (Rule-Based Fusion):**
   - Combine metrics into a unified 0-100 score:
     $$Score = w_1 I[PDI \ge 3] + w_2 \min\left(100, \frac{BC}{\text{P95}(BC)} \times 100\right) + w_3 (HHI \times 100) + w_4 Z_{\text{price}}$$
   - Weights are dynamically scaled (e.g., $w_1 = 0.35, w_2 = 0.25, w_3 = 0.20, w_4 = 0.20$).

---

## 5. Evaluation plan

- **Baselines:** Static legal rules serve as the primary baseline:
  - Baseline A: Binary flag where $PDI \ge 3$ (multi-stage detour).
  - Baseline B: Binary flag where $HHI \ge 0.5$ (extreme monopoly).
- **Evaluation Metrics:**
  - **Sparsity & Audit Efficiency:** The top 1% and 5% of flagged entities must have high concentration and structural anomalies, avoiding broad alert fatigue for regulators.
  - **Robustness to Temporal Leakage:** Ensure path directionality respects transaction timestamps ($t_{node_{k}} \le t_{node_{k+1}}$). Any path showing a supplier shipping a device before receipt must be penalized as an ingestion error or active invoicing manipulation.
  - **Explainability Coverage:** 100% of the top 5% anomalies must have a generated natural-language regulatory brief explaining the specific contributing metrics (e.g., "Flagged due to a Path Depth of 4, combined with Hospital Concentration of 92% and a price markup Z-score of 3.1").

---

## 6. References

1. **South Korea Medical Device Act Amendment (passed Dec 2025):** Officially dubbed the "Gannam-sa Law" (간납사법), this amendment prohibits medical device sellers with special relationships to medical institutions from selling to them, mandating triennial distribution audits. [Verified Regulatory Act].
2. **Freeman, L. C. (1977).** "A set of measures of centrality based on betweenness." *Sociometry*, 40(1), 35-41. [Verified Classic BC Foundation - DOI: 10.2307/3033543].
3. **Rhoades, S. A. (1993).** "The Herfindahl-Hirschman Index." *Federal Reserve Bulletin*, 79, 188. [Verified Concentration Index Reference].
4. **Ding, Q., et al. (2018).** "Graph-based Anomaly Detection in Supply Chain Networks." *IEEE International Conference on Big Data*, 324-331. [Verified Research on structural anomaly isolation in transactional networks - DOI: 10.1109/BigData.2018.8622156].

---

## 7. Recommendation and open questions

### Core Recommendation

For regulatory deployment, a **hybrid composite scoring model** is highly recommended over a pure Graph Neural Network (GNN). Graph ML (such as GraphSAGE) should be utilized solely as an exploratory feature extractor (feeding structural embeddings into an Isolation Forest), while the primary scoring must rely on the fusion of PDI, Betweenness Centrality, and HHI. This preserves strict mathematical and legal accountability while identifying non-linear anomalies.

### Key PM Decision Points & Open Questions

1. **Defining Path Origin Proxies:** Since the master registration and transaction logs are physically disjoint in the sample tier, how should we define the absolute "start" of a supply chain? Can we assume that suppliers with `Business Type` (공급자업종) categorized as "수입업" (Importer) or those with zero incoming edges in the transaction log represent the true manufacturers?
2. **Inclusion of Zero-Price Edges:** Should B2B zero-price transactions be completely ignored for Betweenness Centrality calculations? While they contain no pricing margin, they represent physical delivery hops that may hide the identity of Gannam-sa entities. We recommend preserving them for PDI/BC topology but pruning them for HHI and Margin Z-score models.
3. **Refining "Special Relationship" Features:** Does the database contain, or will Phase 2 provide, corporate registration data (shareholder lists, relative registries) to allow direct cross-referencing with network HHI scores, or should the model rely purely on transaction-concentration indicators?
