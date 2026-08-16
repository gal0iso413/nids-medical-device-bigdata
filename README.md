# NIDS local analysis workspace

This repository's active product paths are local and offline. They do not
constitute a public-service release and must not expose source data or raw
analysis artifacts.

## Start here

- [Run local analysis directly](docs/data/local-analysis-turnkey-runbook.md)
- [Run the offline kit on another PC](tools/offline/analysis-kit/README.md)
- [Class 1 React interface](web/class1_internal/)
- [Class 3 React interface](web/class3_public/)

Class 1 runs the GAD-NR offline anchor runner over verified monthly Parquet,
then publishes a restricted-safe handoff for the React interface. Class 3
exports local analysis JSON from the same verified monthly Parquet for its
React interface. Class 2 is unchanged by this cleanup.

## Authoritative documents

1. `README.md`
2. `docs/data/local-analysis-turnkey-runbook.md`
3. `docs/decisions/`
4. `docs/specs/`

Documents in `shared_docs/structured/` are historical problem and data context
only; they do not define a runtime entrypoint.

Do not commit Excel, Parquet, SQLite, generated JSON, model results, ZIP,
wheel, executable, or site-specific configuration files. Do not interpret a
sample Excel request as approval to change the UI. Field-data validation and
its results are not production or public approval.
