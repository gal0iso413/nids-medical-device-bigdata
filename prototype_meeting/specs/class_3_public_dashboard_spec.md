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

1. Select business type: manufacturer, importer, distributor/lessor, medical
   institution, pharmacy/wholesaler, or other.
2. Select broad region.
3. Select one or more product groups.
4. Select a non-sensitive size band.
5. Review the generated anonymous cohort definition and cohort size.
6. Inspect four result views.

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

### 품목 기회 지도

Axes:

- x: recent quantity or transaction growth
- y: supplier concentration (HHI or top-share)

Bubble:

- aggregate market scale band

Plain-language quadrants:

- growing / many suppliers
- growing / concentrated
- slowing / many suppliers
- slowing / concentrated

The word “opportunity” means “area worth reviewing,” not a forecast or
investment recommendation.

### 비슷한 기업군

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

If clustering is unstable, too small, or privacy-unsafe, fall back to rule-based
cohorts defined by the selected profile.

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

The meeting prototype includes one deliberately suppressed profile
(`기타 관련기관` + `제주권` + `소규모`) so experts can assess the privacy
recovery flow.

## Acceptance tasks

Participants should be able to:

1. Create a profile without entering a company name.
2. explain which organizations are included in the comparison group.
3. state whether one product area is growing or slowing.
4. identify whether its supplier market is concentrated.
5. choose one follow-up question.
6. explain why a named company's exact value is unavailable.
