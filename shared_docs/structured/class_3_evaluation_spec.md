# Class 3 — Impact Evaluation Specification

> **Status:** Historical MCDM/impact-evaluation mandate; superseded for product implementation.
> **Authority:** Retained as source context only. `docs/decisions/class3-rebuild-decision.md` and `docs/specs/class3-company-product-comparison.md` govern current Class 3 implementation.

## Scope

- Multi-criteria decision frameworks
- Feature normalization and portfolio mapping
- Stakeholder-facing reporting (post-approval)

## PM refinements (optional)

- Criteria names, weights, and sensitivity rules
- Public report redaction policy
- Portfolio segmentation buckets

## Body

### Initial Document (제안서)

#### 1. Problem Definition & Operational Objectives
- **Business Pain Points:** Without prioritization among various medical devices, it is difficult to effectively manage and respond to supply chain issues.
- **Operational Objectives:** Identify core medical devices with massive ripple effects during a supply disruption. Categorize items into High, Medium, and Low impact to prioritize supply chain management and stock diversification.

#### 2. Input Data & Feature Dimensions
- **Data Sources:** - Internal: UDI Product Info, Manufacturer/Importer Info, Supply Details Report.
  - External: Medical Institution Info (Type, Scale).
- **Specific Feature Variables:**
  - `device_class` [의료기기 등급 (1~4)]: Base weight for product risk.
  - `implantable_yn` [인체이식형 여부]: Upward adjustment of impact.
  - `single_use_yn` [일회용 여부]: Determines inventory exhaustion sensitivity.
  - `traceable_yn` [추적관리대상 여부]: High-risk item classification.
  - `reimburse_yn` [요양급여 대상 여부]: Estimates usage scale.
  - `reimburse_code` [요양급여 코드]: Links to health insurance claim volumes to recalibrate impact based on actual usage.
  - `overseas_manufacturer` [해외제조원 정보]: Supply chain vulnerability.
  - `set_component_info` [한 벌 구성 정보]: Measures irreplaceability.
  - `combination_component_info` [조합의료기기 구성]: Complex interdependency.

#### 3. Algorithmic Modeling & Analytical Tech Track
- **Multi-Criteria Decision Making (MCDM):**
  - Scoring Formula: $ImpactScore_i = \sum_{k=1}^{K} W_k \times S_{ik}$.
  - Evaluation Indicators & Weights ($W_k$): Total Supply Qty (0.25), Number of supplied institutions (0.20), Top N Company Share/Monopoly (0.15), Number of similar substitute products (0.20), Device Class (0.10), Specific distribution path ratio (0.10).
- **Heuristic Calibrations:** Correction coefficients are systematically applied to MCDM outputs for implantable devices, traceable targets, and imported single-use items to boost their final impact score.

#### 4. System Interface & Output Deliverables
- **Outputs / Strategic Classifications:**
  - High Impact ($ImpactScore \ge P_{75}$): Strongly recommend strategic stockpiling and supply chain diversification.
  - Medium Impact ($P_{50} \le ImpactScore < P_{75}$): Placed under regular monitoring.
  - Low Impact ($ImpactScore < P_{50}$): Designated for general management.

---

### Main Document (착수보고서)

#### 1. Problem Definition & Operational Objectives
- **Business Pain Points:** High dependency on foreign imports for essential, life-saving medical devices (e.g., 87.5% foreign dependency in tertiary hospitals) poses a critical national health security threat. Existing systems use a 1-dimensional, volume-based ranking that conflates critical irreplaceable devices with generic high-volume consumables, thereby misallocating strategic R&D and stockpiling resources.
- **Operational Objectives:** Orthogonalize evaluation axes into Clinical Impact (Severity) and Supply Risk (Likelihood) to establish a 2D portfolio map. This enables intuitive, persona-based classification of devices for precision policy execution (e.g., strategic stockpiling, R&D localization, diversification).

#### 2. Input Data & Feature Dimensions
- **Supply Risk Features (X-Axis):**
  - `Manufacturer Country` [제조원국가]: Overseas import dependency indicator.
  - `UDI` [표준코드(UDI)]
  - `Supplier` [공급자 / 공급한자 업체일련번호]
  - `Supply Qty` [공급수량]: Used for calculating Top N company monopoly concentration.
- **Clinical Impact Features (Y-Axis):**
  - `Device Class` [등급]: Baseline risk level.
  - `Implantable Status` [인체이식 의료기기 여부]: Multiplier for clinical severity.
  - `Single-use Status` [일회용 의료기기 여부]
  - `Item Group` [품목군] & `UDI` [표준코드(UDI)]: Identifies substitutability (absence of alternatives).
- **Market Impact / Scale Features:**
  - `Supply Qty` [공급수량] & `Supply Amount` [공급금액]: General market volume.
  - `Medical Institution Code` [요양기관기호(의료기관)]: Breadth of hospital coverage.

#### 3. Algorithmic Modeling & Analytical Tech Track
- **Phase 1: Multi-Criteria Decision Making (MCDM):**
  - Evaluates devices by applying customized weights ($W_k$) to variables. High weights are assigned to supply scale (0.25) and substitutability (0.20), while generic distribution dependencies receive lower weights (0.10).
- **Phase 2: Two-Axis Orthogonalization:**
  - Transforms linear scores into a 2D Kraljic Matrix to separate systemic dependencies (X-axis) from clinical severity (Y-axis).
- **Phase 3: AI Persona Clustering (Unsupervised Learning):**
  - Utilizes K-Means and Gaussian Mixture Models (GMM) to automatically identify meaningful semantic clusters (e.g., "Foreign-dependent monopoly group") instead of relying on arbitrary human thresholds.

#### 4. System Interface & Output Deliverables
- **4-Quadrant Portfolio Dataset:** Classifies items into Strategic (Quadrant 1), Bottleneck (Quadrant 2), Routine (Quadrant 3), and Leverage (Quadrant 4) items for policy execution.
- **AI Persona Clustering Report:** Defines cluster characteristics and itemized lists that require focused policy intervention.
- **Interactive Supply Chain Risk Dashboard:** An interactive visual system allowing dynamic simulation of MCDM weights and visual drill-down functionality where item sizes correspond to supply volume.

---
