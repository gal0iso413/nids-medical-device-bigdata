# Onsite Visit 1 — Production Data Calibration Summary

> **Status:** Active — factual ground truth from NIDS production data (2026-06-18).  
> **Authority:** Factual calibration for all agents; does not override per-agent `class_*_*_spec.md` mandates.  
> **Source run:** Visit 1, Day 2, attempt 4 — supply 202601–202604, all sheets (`2601~2604 (full sheet)`).

## Visit context

| Item | Value |
|------|-------|
| Visit date | 2026-06-18 |
| Smoke test | PASS |
| Canonical run | Supply months 202601–202604; master single file through 202605 |
| Kit validation | 106 PASS / 14 FLAG / 0 FAIL |
| Export reference | `onsite_exports_2026-06-18.json` (archived deliverables; not in repo) |

### Production data inventory (onsite)

| Dataset | Files | Rows (observed) | Columns |
|---------|-------|-----------------|---------|
| Master (통합정보등록) | 1 workbook, 3 sheets merged | ~2,625,652 | 93 |
| Supply (공급내역보고) | 12 workbooks, all sheets merged | 12,000,000 | 71 |

Supply period in this run: **20260101–20260430** (4 months). Full NIDS holdings span supply from **2020-08** (10-day tranches) through **2026-04**; master through **2026-05**.

## Success gate — join feasibility

| Check | Result | Status |
|-------|--------|--------|
| `composite_3key_join` | 11,996,981 / 12,000,000 (**99.97%**) | **PASS** |
| `naive_join_before_clean` | 99.97% (no `.0` float artifact issue) | PASS |
| `numeric_normalized_join` | 99.97%; lift vs string-clean = 0% | PASS |
| `two_key_inflation` | 99.97% | PASS |
| `udi_only_inflation` | 12,843,175 rows (**107.03%** of supply) | **FLAG** |

**3-key fields:** Master — `의료기기품목일련번호`, `모델일련번호`, `UDIDI일련번호`. Supply — `의료기기품목일련번호`, `모델일련번호`, `UDI-DI 일련번호`.

UDI-only inflation indicates one UDI-DI maps to multiple master license rows; use 3-key join for modeling, not UDI-only.

## Dictionary alignment

- Master join keys: all present (PASS)
- Supply join keys: all present (PASS)
- Master column count: 93 (PASS)
- Supply column count: 71 (PASS)
- Float-suffix / leading-zero key artifacts: none detected (PASS)

## Column null rates (production)

### Master

| Column | Null rate | Note |
|--------|-----------|------|
| 제조원국가 | 99.6% | FLAG — not usable for country segmentation |

### Supply

| Column | Null rate | Note |
|--------|-----------|------|
| 요양기관기호(의료기관) | 54.6% | FLAG — limits hospital-endpoint graph coverage |
| 로트번호 | 20.1% | moderate |
| 일련번호 | 60.0% | FLAG |
| 제조연월 | 66.9% | FLAG |
| 사용기한 | 25.1% | moderate |

## Quality flags (all runs)

| Flag | Detail | Modeling impact |
|------|--------|-----------------|
| `price_sanity_공급단가` | max ≈ 6.07×10¹⁴ KRW; 161 over-cap; 1 barcode-like (>1e12) | Cap/winsorize before price Z-score or amount aggregates |
| `price_sanity_공급금액` | max ≈ 6.07×10¹⁵ KRW; 924 over-cap; 1 barcode-like | Same — affects HHI and monthly totals if not sanitized |
| `udi_only_inflation` | 107.03% | Dedupe strategy required when aggregating by UDI |
| `class1_import_proxy` | 제조원국가 null 99.63%; import 업종 rows 954,257 | Import proxy unreliable from master country field |
| `class1_path_feasibility` | 요양기관기호 null 54.58% | Graph paths to hospital incomplete for ~half of rows |
| `class2_expiry_field_제조연월` | null 66.87% | Survival/expiry features degraded |
| `class2_master_lifecycle_*` | 허가일자, 품목취소취하여부, UDIDI사용종료여부, 위탁제조자, 해외제조원 — **column missing** from master export | Lifecycle modeling needs NIDS field addition or alternate source |
| `class3_master_field_*` | 한벌구성여부, 조합의료기기여부, 요양급여코드 — **column missing** from master export | MCDM reimbursement/combination flags unavailable in current master |

## Class readiness snapshot

| Class | Ready for Phase 1 EDA on top7? | Key constraint |
|-------|-------------------------------|----------------|
| 1 — Anomaly / graph | Yes, with caveats | Hospital code 54.6% null; price outliers need sanitization |
| 2 — Forecast / survival | Yes, with caveats | 4-month window in run; 제조연월 67% null; master lifecycle cols missing |
| 3 — Impact / MCDM | Yes, with caveats | HHI computable per 품목군; 3 master MCDM cols missing; UDI dedupe needed |

## Drift vs local top7 sample

Local `shared_data/top7_*` workbooks are a **small stratified sample** (~221 master rows, ~704k supply rows). Agents must treat onsite metrics as **production calibration targets** when interpreting top7 EDA — expect higher volume, confirmed join rates, and null-rate patterns above.

## Open questions (PM / NIDS)

Document answers in agent `notes/` or PM tracker as resolved:

1. Are extreme 공급단가/공급금액 values data entry errors or valid edge cases?
2. Why does UDI-only join exceed 100% — multiple licenses per UDI-DI by design?
3. Will NIDS add missing master columns (한벌구성여부, 조합의료기기여부, 요양급여코드, lifecycle fields)?
4. Is 요양기관기호 null expected for non-hospital supply forms (B2B, pharmacy)?

## Agent pointers

| Agent | Detailed profile |
|-------|------------------|
| Class 1 | `class_1_anomaly_detection/notes/eda_profile_onsite_2026-06-18.md` |
| Class 2 | `class_2_supply_forecast/notes/eda_profile_onsite_2026-06-18.md` |
| Class 3 | `class_3_impact_evaluation/notes/eda_profile_onsite_2026-06-18.md` |
