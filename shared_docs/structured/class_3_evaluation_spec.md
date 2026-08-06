# Class 3 — Anonymous Cohort Dashboard Specification

> **Status:** Active — final model concept locked (meeting innovation pivot).
> **Authority:** Supersedes `official/` interpretations for Agent 3 analytical mandate when in conflict.

## Scope

- Internal Streamlit **anonymous peer / market cohort dashboard** (firm-oriented IA, internal deployment this contract)
- Rule-based cohorts only (업종 × 권역 × 품목군); **no** unsupervised clustering typology in v1
- **No** entity risk scores, GNN scores, or named-company search in Class 3
- Prior MCDM / Kraljic impact-matrix product surface is **retired**

## Purpose framing

- Help reviewers understand **peer-group aggregates** and product-name market statistics derived from supply reports.
- Not a public ranking of firms; not sales data; not a product registration index.
- “내 회사” authenticated mode: **deferred** — config hooks only (no implementation).

## Primary journey (wizard)

1. Select **업종**, **주 활동 권역**, **품목군** (product group — not item name).  
2. **기업군 리포트:** 거시 metrics + trend → 진단 narrative.  
3. **품목군 검토 지도:** concentration (HHI) × recent growth; bubble ≈ supplier-count band.  
4. **관심 의료기기:** multi-select **품목명** portfolio compare (aggregate stats only).

## Privacy and publication boundary

- No real company name / registration / hospital code as primary outputs.
- Cohort size / thin-history / suppression rules when aggregates are unsafe.
- Named end-to-end product path for manufacturers is **out of scope** here (Class 1 internal only if needed).

## Data limitations (mandatory UI callouts)

- System is based on **공급내역보고** (supply reports), not retail **판매량**.
- Non-reportable / out-of-scope device categories must be tagged (report-scope filters).
- Coverage gaps (e.g. incomplete hospital endpoints) must be stated.

## Data path

1. Prefer agent-local Parquet materialized from top7 (or Class 1 shared materialize pattern).  
2. Offline cohort aggregates → UI artifact JSON/CSV under `class_3_impact_evaluation/output/ui/`.  
3. Streamlit reads artifacts only.

## Deferred hooks (A12)

- `my_company_mode_enabled: false` in config  
- Placeholder keys for authenticated firm id — unused in v1  

## Historical bodies (제안서 / 착수보고서) — archive only

Earlier MCDM weights, Kraljic 2D matrix, and persona clustering mandates are **superseded** by this cohort-dashboard product. Keep text below for audit; do not implement as current Class 3 UI.

### Archive — Initial Document (제안서)

MCDM impact scoring and High/Medium/Low impact bands.

### Archive — Main Document (착수보고서)

Supply-risk vs clinical-impact axes; Kraljic quadrants; K-Means/GMM persona clustering.

---
