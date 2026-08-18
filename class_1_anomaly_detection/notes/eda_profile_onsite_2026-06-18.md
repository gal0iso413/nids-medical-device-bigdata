# Data Profile — Onsite Visit 1 (Class 1)

> **Agent:** class_1_anomaly_detection  
> **Date:** 2026-06-18  
> **Workbooks profiled:** NIDS production — master ×1, supply ×12 (202601–202604, all sheets)  
> **Source:** `onsite_exports_2026-06-18.json` (Visit 1, attempt 4)

## 1. Executive summary

- Production run: **12,000,000** supply rows; **3-key join 99.97%** — baseline join trust established.
- Graph node cardinality is rich: 공급자 9,546; 공급받은자 62,396; 거래처 코드 255,971; 요양기관기호 64,027.
- Hospital-segment pricing (의료기관에 공급, n=5,455,891): unit-price null **3.68%**, zero-price **15.72%** — usable with zero handling.
- **FLAG:** 요양기관기호 null **54.58%** — limits end-to-hospital path construction for ~half of transactions.
- **FLAG:** 공급단가/공급금액 extreme outliers (max >1e12) — sanitize before Z-score / margin features.
- **FLAG:** 제조원국가 null **99.63%** on master — import-country proxy not viable.
- Trace fields: 로트번호 20.1% null; 일련번호 59.97% null; UDI-PI 11.44% null; 표준코드(UDI) 0% null.

## 2. Workbook inventory

| Role | Count | Rows | Cols |
|------|-------|------|------|
| Master | 1 file (3 sheets) | ~2,625,652 | 93 |
| Supply | 12 files (all data sheets) | 12,000,000 | 71 |

Period: 공급내역기준연월 202601–202604; 공급일자 20260101–20260430.

## 3. Column profile

### Supply — graph and pricing fields

| Column | Null rate | Cardinality | Flag |
|--------|-----------|-------------|------|
| 공급자 | 0.0% | 9,546 | — |
| 공급받은자 | 0.16% | 62,396 | — |
| 거래처 코드 | 0.16% | 255,971 | — |
| 요양기관기호(의료기관) | 54.58% | 64,027 | extreme_null |
| 공급단가 | 3.68% (hospital seg.) | — | outlier tail |
| 공급금액 | — | — | outlier tail |
| 로트번호 | 20.11% | 620,258 | moderate_null |
| 일련번호 | 59.97% | 3,130,437 | extreme_null |
| 생산식별자(UDI-PI) | 11.44% | — | moderate_null |
| 표준코드(UDI) | 0.0% | — | — |

### Master

| Column | Null rate | Flag |
|--------|-----------|------|
| 제조원국가 | 99.63% | extreme_null |

### Supply form distribution (공급형태)

| Value | Rows |
|-------|------|
| 의료기관에 공급 | 5,455,891 |
| 제조ㆍ수입ㆍ판매(임대)에 공급 | 4,980,318 |
| 약국개설자 또는 의약품도매상에 공급 | 1,127,280 |
| (null) | 395,038 |
| 견본품, 기부용 또는 군납용 등 | 41,473 |

### Supply class distribution (공급구분)

| Value | Rows |
|-------|------|
| 출고 | 11,365,901 |
| 반품 | 584,167 |
| 폐기 | 19,143 |
| 임대 | 15,759 |
| 회수 | 15,030 |

Discard rows (n=19,143): receiver fields 100% null — expected; exclude from graph.

## 4. Dictionary alignment

- All 3-key join columns present on master and supply (PASS).
- Column counts match official dictionaries: master 93, supply 71 (PASS).
- No float-suffix or leading-zero key normalization needed (lift = 0%).

## 5. Join feasibility

| Method | Matched | Rate |
|--------|---------|------|
| 3-key (cleaned) | 11,996,981 / 12,000,000 | 99.97% |
| UDI-only | 12,843,175 rows | 107.03% (inflation) |
| 2-key (item + model) | 11,996,981 | 99.97% |

Use 3-key join for master enrichment; avoid UDI-only joins (license duplication).

## 6. Drift and quality flags

| Check | Status | Detail |
|-------|--------|--------|
| price_sanity_공급단가 | FLAG | max ≈ 6.07×10¹⁴ KRW; 161 over-cap |
| price_sanity_공급금액 | FLAG | max ≈ 6.07×10¹⁵ KRW; 924 over-cap |
| class1_path_feasibility | FLAG | Hospital code missing on 54.58% of rows |
| class1_import_proxy | FLAG | 제조원국가 unusable; 954,257 import 업종 rows in supply |
| udi_only_inflation | FLAG | 107.03% — multiple masters per UDI |

Hospital price null by month: 202601 3.25%, 202602 4.95%, 202603 3.06%, 202604 3.42%.

최초접수일자 + 공급일자 both present: 100% — time-lag feature feasible.

## 7. Recommended next steps

1. Phase 1 EDA on top7: replicate graph cardinality and null-rate checks; compare to production calibration above.
2. Implement price sanitization (cap/winsorize) before `metrics_price_zscore` and amount-based graph weights.
3. Build graph on rows with non-null 요양기관기호 OR use 공급받은자/거래처 코드 as alternate endpoints; document coverage bias.
4. Segment by 공급형태 — hospital pricing rules apply only to 의료기관에 공급 rows.
5. Do not use 제조원국가 for import detection; use supply 업종 proxy with PM acknowledgment.
6. Escalate open FLAGs via `AgentSlacker` if join or null rates on top7 diverge materially from onsite baselines.
