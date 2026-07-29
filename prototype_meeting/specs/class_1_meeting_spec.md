# Class 1 Meeting Specification

## Purpose

Help a domain expert find an organization, understand its immediate supply
relationships, and judge whether the evidence shown is useful for deciding what
to review next.

The prototype does not determine illegality or prove anomalous conduct.

## Primary journey

1. Search for a masked company.
2. Select a result and see its one-hop network.
3. Expand to two hops when additional context is needed.
4. Change the three-month anchor period.
5. Compare transaction count and quantity.
6. Open “확인 근거” to distinguish facts, model signals, and limitations.

## Screen structure

### Search and period

- Large company-name search is the primary control.
- Default example: `C 유통`.
- Anchor period represents a three-month rolling window.
- Scenario selector is facilitator-only context, visually secondary.

### Summary

- incoming organizations
- outgoing organizations
- transaction reports
- supplied quantity
- change versus preceding window

### Network

- Directed arrows show supplier → receiver.
- Default depth is one hop; two hops is optional.
- Edge-width selector: report count or supplied quantity.
- Node-size selector: number of connections.
- Node type uses both color and text legend.
- Selected company uses a strong outline.
- “확인 필요” nodes use a labeled warning marker, not red alone.
- Full-network rendering is prohibited; bounded subgraphs protect readability
  and performance.

### Relationship table

- direction
- connected organization
- organization type
- report count
- supplied quantity
- major product label
- observed change

### Review list

“AI 검토” is renamed **확인 필요 업체**.

Each row includes:

- illustrative 0–100 review priority
- status label
- observed structural evidence
- rule-based supporting evidence
- uncertainty statement
- link back to the network

## Explanation contract

The prototype separates:

1. **관찰된 사실:** counts, path length, concentration, price deviation, lag.
2. **모형의 해석:** unusual compared with learned or peer patterns.
3. **확인할 질문:** a neutral follow-up question for the reviewer.

Supported evidence families:

- **Connection hub:** BC percentile, in-degree, out-degree.
- **Long route:** product-level PDI.
- **Concentration:** hospital-item HHI.
- **Price difference:** robust MAD z-score within product and supply type.
- **Reporting lag:** supply date versus first receipt date.
- **Relationship AI:** normalized GNN/anomaly-model score.

The model score is not a probability. There are no ground-truth fraud labels.
Mock reason percentages are scenario composition values, not explanations
derived from production GNN internals.

## Hub and GNN roles

- The network overview is ordered by BC because it is explicitly a structural
  hub view.
- The “확인 필요 업체” list may be ordered by the recommended GNN/anomaly model.
- The interface must not label GNN rank as BC or imply they are the same.
- GNN evidence may be compared with BC/PDI/HHI/price/lag weak baselines.

## Data feasibility

Current architecture already supports:

- three-month rolling selection
- monthly edge snapshots
- directed multi-product graph
- entity search and one/two-hop ego graph
- count/amount attributes and degree metrics
- BC, PDI, HHI, robust price z-score, time-lag
- GNN score comparison

Prototype adaptations:

- synthetic quantities and counts
- node size by connectivity
- edge width by selected measure
- explicit arrows and Korean legends
- reason-factor presentation

## Mandatory limitations

- Hospital codes are incomplete, so some paths cannot end at identified
  hospitals.
- Invalid/extreme prices must be excluded or replaced using documented
  fallbacks.
- Missing price values reduce price-comparison coverage.
- PDI reflects observed data, not necessarily the complete real-world route.
- Review priority indicates where to inspect, not wrongdoing.

## Acceptance tasks

Participants should be able to:

1. Find `C 유통`.
2. state how many organizations supply to and receive from it.
3. identify the direction of one relationship.
4. explain one reason it appears in the review list.
5. name one limitation before making a decision.
