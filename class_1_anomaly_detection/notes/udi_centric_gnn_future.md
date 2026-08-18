# Future idea — UDI-centric GNN (G1-e, not implemented)

> Status: **documented only**. Production Class 1 uses a **firm-entity** graph GNN (GAD-NR).

## Motivation

A UDI- (or product-composite-) centric graph would place devices or UDI-DI nodes in the topology so path-depth, diversion, and item-specific rerouting anomalies are learned directly, rather than inferred only via firm-level neighborhoods and separate PDI rules.

## Why it is deferred

- Edge count approaches transaction scale (millions on production windows) unless heavily pre-aggregated.
- Memory/time roughly doubles if trained **in addition to** the firm-entity GNN.
- Hospital-endpoint null rates already limit path completeness; UDI graphs inherit that gap.
- Current contract keeps one production GNN (firm) with rules (including PDI) as auxiliary evidence.

## When to revisit

- Firm-graph GAD-NR is stable in production and RAM budget is known.
- Item-group / month pre-aggregation yields a UDI graph that fits offline GPU batch without OOM.
- Policymakers need item-first monitoring that firm scores cannot explain.

## Possible later design (sketch)

1. Nodes: UDI-DI or (item, model, UDI) composites (+ optional firm bipartite layer).  
2. Edges: supply events aggregated by month and counterparty type.  
3. Train separately from firm GAD-NR; map scores back to firms via participation weights.  
4. UI: keep firm review list; offer “product path evidence” panel fed by UDI model or rules.

Do not enable a second full GNN train in v1 without an explicit PM spec change.
