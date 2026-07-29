# Platform and Feasibility Research

## Decision summary

The meeting prototypes should lead with a user task rather than an analytical
method:

1. **Find my context**
2. **Understand what changed**
3. **Identify what to review next**

Class 1 can be represented faithfully with synthetic data because the current
architecture already supports company search, directed ego networks, rolling
windows, BC hub analysis, GNN rankings, and rule-based evidence. Class 3 should
remain a synthetic concept prototype: the available data can support most
proposed aggregate features, but production firm clustering, disclosure
controls, and publication approval do not exist yet.

## Korean public-platform patterns

### KOTRA TriBIG

KOTRA starts from a company or product interest and returns recommended markets
or partners. The useful pattern is not the AI label; it is the short path from
profile input to a ranked, explainable result.

Applied here:

- Class 3 starts with business type, broad region, product interests, and size
  band.
- Results explain why the selected cohort is relevant.
- Recommendations are framed as review questions, not guaranteed outcomes.

Sources:

- KOTRA overseas information:
  <https://kotra.or.kr/subList/20000006759>
- KOTRA TriBIG service description:
  <https://dl.kotra.or.kr/pyxis-api/2/digital-files/5616430f-e0c4-41a9-9d5c-61c44f67c22a>

### KOSIS

KOSIS comparison services use guided steps: choose indicators, choose a region,
then compare. They also limit simultaneous comparisons so the result remains
readable.

Applied here:

- Use a four-field profile wizard instead of a large filter wall.
- Limit the initial Class 3 result to a small number of decision-relevant
  indicators.
- Show definitions next to indicators rather than in a separate manual.

Sources:

- KOSIS visualization services:
  <https://kosis.kr/easyViewStatis/visualizationIndex.do>
- KOSIS regional comparison:
  <https://kosis.kr/visual/economyBoard/economyRegion.do?lang=ko>

### HIRA Open Data

HIRA clearly separates public statistics and APIs from restricted analytical
services and customized anonymous statistics.

Applied here:

- Public Class 3 results are aggregated and anonymous.
- A future authenticated “my company” service must be a separate access mode.
- The UI always identifies data scope, update period, and limitations.

Source:

- HIRA Open Data service overview:
  <https://opendata.hira.or.kr/op/opb/selectHelhMedDataInfoView.do>

### Credit Guarantee Fund BASA

BASA combines peer comparison with plain-language diagnostic comments. Its
strong pattern is “position versus similar organizations,” not a raw statistics
catalog.

Applied here:

- Class 3 uses cohort percentiles and ranges instead of public firm rankings.
- Each result includes an evidence-based interpretation and a suggested
  question to investigate.

Source:

- BASA service information:
  <https://www.basadata.com/main/serviceInfo.do>

## NIDS alignment

NIDS operates the integrated information center to record and manage UDI
registration and supply reporting and to support lifecycle safety management.
The common prototype theme therefore emphasizes traceability, safe
distribution, evidence, and appropriate review rather than commercial
promotion.

Sources:

- NIDS integrated information center:
  <https://www.nids.or.kr/contents.jsp?page=NIDS-003>
- NIDS vision and safety-management role:
  <https://www.nids.or.kr/contents.jsp?page=NIDS-079>

Exact CI colors and assets were not available in the reviewed public material.
The prototype uses a restrained public-service blue/teal palette and must be
updated if NIDS provides an official brand guide.

## Accessibility and public-service UX

The shared interface follows KRDS task-oriented service patterns and KWCAG 2.2:

- Korean-first, concise labels
- 16 px or larger body text
- 44 px minimum interactive targets
- text/background contrast of at least 4.5:1
- no meaning communicated by color alone
- visible focus, keyboard navigation, and logical heading order
- no automatically moving or playing content

Sources:

- KRDS overview:
  <https://v04.krds.go.kr/guide/outline/outline_01.html>
- KRDS structure:
  <https://v04.krds.go.kr/guide/outline/outline_02.html>
- NIA KWCAG 2.2 techniques:
  <https://nia-a11y.github.io/kwcag22tech/>

## Active-data feasibility check

Checked on 2026-07-13 using the active top7 workbooks only.

### Observed local data

- Master: 221 rows, 93 source columns.
- Supply: 704,315 rows, 71 source columns plus two loader quality flags.
- Supply period: 2020-08 through 2026-05 (70 months).
- Supplier serial/name/type: present with no nulls.
- Receiver serial: 1.08% null; receiver name/type: 0.16% null.
- Hospital code: 47.85% null in the local sample.
- Supply quantity: 0.01% null.
- Supply amount: 17.16% null; unit price: 21.51% null.
- Supplier and receiver region codes: 17 categories; receiver region 1.08%
  null.
- Supply and receipt dates: present with no nulls.
- Local sample contains only seven selected items/product groups, so it is not
  representative of the national product market.

Production calibration remains authoritative where it differs from the local
sample: 12 million supply rows in the onsite run, a 99.97% three-key join,
54.6% hospital-code nulls, extreme price values requiring sanitization, and
manufacturer country 99.6% null.

### Class 1 feasibility

Supported by current code and data:

- stable entity resolution using company serial, registration number, hospital
  code, and name fallbacks
- directed supplier-to-receiver graph
- one- and two-hop ego search
- three-month rolling windows and monthly snapshots
- transaction count and cleaned amount edge attributes
- inbound/outbound degree and BC hub ranking
- PDI, hospital-item HHI, robust price z-score, and reporting time-lag evidence
- five GNN/anomaly model score families and weak-baseline comparison

Important limits:

- Hospital endpoint coverage is incomplete.
- GNN scores have no ground-truth fraud labels and must not be presented as
  proof.
- PDI paths may be truncated by missing endpoints.
- Price evidence is unavailable for rows without valid prices.
- A public graph must use synthetic or strongly protected identifiers.
- Loading the 243 MB Excel workbook took approximately eight minutes locally;
  a meeting UI must use precomputed data.

### Class 3 feasibility

Feasible from current fields after production engineering:

- profile dimensions: business type, broad region, product group, and
  transaction-derived size band
- monthly cohort trends and peer percentiles
- product-group supplier count, HHI, and top-share
- product, receiver-type, region, and device-class mix features

Not yet a production capability:

- firm entity-resolution pipeline in Class 3
- validated firm clustering
- publication/redaction service
- minimum-cell and dominance enforcement
- public field allowlists
- authenticated private-company mode

Unsafe or unreliable inputs:

- manufacturer country
- exact firm or counterparty names and identifiers
- exact detailed addresses
- raw transaction paths
- claims of national representativeness from the top7 sample

## Privacy research

Korean statistical guidance requires protecting identifiable individuals,
businesses, corporations, and organizations. Small-cell suppression,
complementary suppression, rounding, noise, and dominance rules are established
statistical disclosure-control techniques.

Prototype policy:

- no real firm lookup
- synthetic data only
- provisional cohort floor `k >= 5` in the specification
- no raw export
- no exact public firm values
- NIDS privacy/legal approval required before production thresholds are fixed

Sources:

- Statistics Act provisions:
  <https://kosis.kr/FileServlet?file=%2F20170511%2FserviceInfo%2FserviceInfo_06Form.jsp%2F%ED%86%B5%EA%B3%84%EB%B2%9530%2C31%2C33%EC%A1%B0.pdf&mode=boarddown&orgname=%ED%86%B5%EA%B3%84%EB%B2%9530%2C31%2C33%EC%A1%B0.pdf>
- Government de-identification guidance:
  <https://www.korea.kr/archive/expDocView.do?docId=37095>

`k >= 5` is a conservative prototype default, not a legal safe-harbor.
