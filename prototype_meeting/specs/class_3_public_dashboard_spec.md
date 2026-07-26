# Proposed Class 3 Public Dashboard Specification

## Status

This is a PM proposal for the meeting prototype. It does not replace
`shared_docs/structured/class_3_evaluation_spec.md`, unlock Class 3 Phase 2–3,
or authorize publication of operational data.

## Product decision

Class 3 pivots from a regulator-facing impact matrix to a public,
firm-oriented **anonymous peer and market dashboard**.

Initial mode:

- user selects a non-identifying business profile
- system returns an aggregate comparison cohort
- no real-company search or public firm-level output

Possible later mode:

- authenticated “내 회사” results using private firm data
- separate authorization, service boundary, and privacy review

## Difference from the NIDS annual report

Annual-report totals may appear only as context. The dashboard's distinct value
is derived, user-relative information:

- peer position rather than a national count
- recent direction rather than a single annual snapshot
- growth/change versus concentration
- product and receiver mix
- similar-business patterns
- evidence-linked questions for business planning

## Primary journey

**Meeting innovation:** firm-first, then optional device statistics.

1. Select 업종, region, and **품목군** (product group — not item name).
2. Read the firm report Top-down: **거시 → 쉬운 사실 → 진단** (privacy one-liner visible).
3. Review the **품목군 검토 지도** (open by default after report): concentration × growth × supplier-count bubbles.
4. Optionally open **관심 의료기기 알아보기** (also available under diagnosis).
5. Search **품목명** (item name) via typeahead / 추천 검색어 (about 4 chips; linked group first). Do not ask for
   device class or region on this step.
6. Read **품목명 aggregate statistics** (activity, concentration, supplier
   scale, receiver mix, optional flag-prevalence details, diagnosis). This is **not** a
   product-registration index card.

**품목군 vs 품목명:** Firm filters use 품목군. Device sequel uses 품목명.
They must not be conflated in UI copy or mock keys.

Legacy / baseline tab views remain available on the existing prototype page.

## Result views

### 내 그룹 한눈에 보기

- cohort size
- transaction-direction trend
- supplied-quantity trend
- active-product breadth
- receiver-type breadth
- percentile band against the cohort

Percentile labels use plain language:

- lower 25%
- middle 50%
- upper 25%

They are not public firm rankings.

### 품목군 검토 지도

Axes (P1.5):

- x: supplier concentration (HHI; low → high)
- y: recent transaction-activity growth (%)

Bubble:

- unique supplier count bands (소 &lt;15 · 중 15–34 · 대 ≥35), with on-chart legend

The map is for review, not a forecast or investment recommendation.
Avoid calling it an “opportunity” map in participant-facing Korean copy.

### 기업군 유형 참고 (optional depth)

Future production clustering may use normalized composition features:

- product-group mix
- receiver-type mix
- region mix
- device-class mix
- transaction-frequency band
- quantity band
- product breadth

Display semantic profiles such as “regional hospital-focused suppliers.”
Do not expose algorithm IDs like `cluster_2` as the primary label.

**Meeting wording (P0):** Primary UI says **해당 기업군** (filter-matched
cohort). Clustering typology is secondary “기업군 유형 참고,” not the main
promise. If clustering is unstable, too small, or privacy-unsafe, fall back to
rule-based cohorts defined by the selected profile.

### 무엇을 확인할까요?

Rules produce neutral prompts tied to displayed evidence, for example:

- “Your selected product group's transactions increased while supplier
  concentration also increased. Check whether alternative sourcing options
  changed.”
- “Hospital-directed supply share changed more than the peer range. Check
  whether this reflects a reporting or channel change.”

No unsupported generative recommendation is presented as fact.

## Available field mapping

Feasible fields:

- supplier/receiver business type
- supplier/receiver broad region
- item and product group
- device class and selected regulatory flags
- supply month and date
- transaction/report count
- supply quantity
- cleaned aggregate amount where valid
- receiver type
- stable internal company serial for private aggregation

Do not depend on:

- manufacturer country
- detailed hospital coverage as a complete measure
- missing master combination/reimbursement-code fields
- external claims or demand data not supplied to the project

## Future analytical pipeline

1. Resolve firm identity using system company serial first.
2. Filter valid forward-flow rows and sanitize numeric fields.
3. Aggregate to firm-month and market-month tables.
4. Build scale-independent composition features.
5. Coarsen dimensions and apply publication rules.
6. Compare candidate cluster counts and algorithms.
7. Test stability across resamples and periods.
8. Require minimum cluster/cohort size.
9. Profile and name groups from dominant characteristics.
10. Publish only approved aggregate products.

## Publication and disclosure gate

Prototype defaults, subject to NIDS privacy/legal approval:

- aggregate on the server before delivery
- minimum displayed cohort/cell size `k >= 5`
- primary and complementary small-cell suppression
- coarsen region/product/size dimensions until safe
- publish cohort sizes, percentiles, growth, supplier counts, and group shares as
  approved ranges rather than exact public values
- round displayed amounts when an approved aggregate amount is necessary
- block differencing-prone filter combinations
- test dominance when one or two firms account for most of a value
- no row-level export
- no exact public firm amounts or ranks
- no names, registration numbers, license numbers, hospital codes, detailed
  addresses, contacts, lots, or serial numbers
- audit every released data product

The minimum cell threshold is not sufficient by itself and is not a legal
safe-harbor.

## Meeting mock-data contract

`mock_data.json` contains:

- profile option lists
- cohort definitions and safe cohort counts
- monthly aggregate series
- benchmark metrics with percentile bands
- opportunity-map product records
- semantic similar-group profiles
- evidence-linked review prompts
- methodology and limitation text

It must not contain real identifiers or values copied from the active
workbooks.

The meeting prototype includes deliberately sparse profile demos so experts can
assess recovery flows:

- `기타` + `비수도권` — full suppress (cohort below publication floor)
- `기타` + `수도권` — thin history (metrics shown; monthly trend hidden)

Profile regions are `수도권` / `비수도권` / `전국`. The opportunity map uses
x = supplier concentration (HHI), y = recent activity growth, bubble = supplier
count bands.

## Acceptance tasks

Participants should be able to:

1. Create a profile without entering a company name.
2. explain which organizations are included in the comparison group.
3. state whether one product area is growing or slowing.
4. identify whether its supplier market is concentrated.
5. choose one follow-up question.
6. explain why a named company's exact value is unavailable.
