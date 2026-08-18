# Data Profile — Onsite Visit 1 (Class 3)

> **Agent:** class_3_impact_evaluation  
> **Date:** 2026-06-18  
> **Workbooks profiled:** NIDS production — master ×1, supply ×12 (202601–202604, all sheets)  
> **Source:** `onsite_exports_2026-06-18.json` (Visit 1, attempt 4)

## 1. Executive summary

- HHI and top-3 supplier share computed for **69 품목군** — MCDM concentration inputs are viable.
- Clinical flags on master (joined): 등급, 인체이식형 의료기기여부, 추적관리대상, 희소의료기기여부 — all **0% null**.
- **FLAG:** Master columns 한벌구성여부, 조합의료기기여부, 요양급여코드 — **missing** from export (not null).
- **FLAG:** UDI-only join inflation 107.03% — dedupe before supplier-level HHI aggregation.
- **FLAG:** 공급금액 outliers — sanitize before amount-weighted concentration indices.
- Concentration varies widely: 부목 HHI 47 (competitive) vs 콘돔 HHI 8,049 (near-monopoly top-3 96.8%).

## 2. Workbook inventory

| Role | Count | Rows | Cols |
|------|-------|------|------|
| Master | 1 file | ~2,625,652 | 93 |
| Supply | 12 files | 12,000,000 | 71 |

Window: 202601–202604. Join rate 99.97% on 3-key.

## 3. Column profile

### Master clinical flags (post-join)

| Column | Null rate |
|--------|-----------|
| 등급 | 0.0% |
| 인체이식형 의료기기여부 | 0.0% |
| 추적관리대상 | 0.0% |
| 희소의료기기여부 | 0.0% |

### Master MCDM fields — missing

| Column | Status |
|--------|--------|
| 한벌구성여부 | missing |
| 조합의료기기여부 | missing |
| 요양급여코드 | missing |

## 4. Dictionary alignment

Join keys and 품목군 present on supply. Master reimbursement/combination flags absent — gap vs official dictionary expectations.

## 5. Join feasibility

| Method | Rate | Note |
|--------|------|------|
| 3-key | 99.97% | Use for enrichment |
| UDI-only | 107.03% | Inflation — multiple licenses per UDI |

## 6. Drift and quality flags — HHI by 품목군 (selected)

Full 69-group metrics in onsite export. Representative extremes:

| 품목군 | Models | UDI-DI | Hospitals | HHI (amount) | Top-3 share |
|--------|--------|--------|-----------|--------------|-------------|
| 부목 | 3,454 | 4,084 | 5,037 | 47.1 | 6.0% |
| 외과용품 | 10,854 | 14,096 | 7,996 | 302.6 | 24.6% |
| 정형용품I(관절류 등) | 38,268 | 39,780 | 1,322 | 173.7 | 18.8% |
| 봉합사 및 결찰사(II) | 4,159 | 5,733 | 14,219 | 300.8 | 20.8% |
| 인체조직 또는 기능 대치품 | 2,163 | 12,362 | 13,405 | 370.0 | 28.9% |
| 눈 적용 렌즈(I) | 522 | 1,646 | 134 | 3,952.6 | 89.3% |
| 생명유지 장치 | 339 | 378 | 677 | 2,885.9 | 63.4% |
| 치과처치용 기계기구 | 529 | 552 | 1,725 | 5,347.2 | 92.5% |
| 콘돔 | 32 | 35 | 260 | 8,048.8 | 96.8% |
| 조직병리 검사기기 | 185 | 231 | 23 | 4,181.2 | 96.6% |

Groups with null HHI (소프트웨어, 시력보정용 안경): insufficient supplier diversity for amount-weighted index.

| Check | Status |
|-------|--------|
| class3_master_field_한벌구성여부 | FLAG — missing |
| class3_master_field_조합의료기기여부 | FLAG — missing |
| class3_master_field_요양급여코드 | FLAG — missing |
| price_sanity_공급금액 | FLAG — sanitize before HHI |
| udi_only_inflation | FLAG — dedupe strategy required |

## 7. Recommended next steps

1. Phase 1 EDA on top7: compute per-품목군 HHI; compare rank order to onsite calibration table.
2. Apply amount sanitization (same rules as onsite kit) before HHI — raw max >1e15 KRW observed.
3. Aggregate at supplier × 품목군 after 3-key dedupe; never UDI-only for concentration metrics.
4. Use 등급 / 추적관리대상 / 희소의료기기여부 as MCDM criteria weights — confirmed 0% null.
5. Escalate missing 한벌구성여부, 조합의료기기여부, 요양급여코드 to PM/NIDS before reimbursement-aware scoring.
6. Flag 품목군 with HHI > 2,500 and top-3 share > 80% as high-priority monopoly candidates for impact evaluation.
