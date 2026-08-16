# Class 3 rebuild decision

> Status: active product decision and cleanup status
> Updated: 2026-08-16

## Active product boundary

Class 3 is a company/product-group comparison analysis. Its active route is
verified monthly Parquet, `data_pipeline.offline.class3_analysis_export`, and
the React interface in `web/class3_public/`. The browser consumes only the
local analysis JSON adapter; it does not load Excel, Parquet, SQLite, or raw
source artifacts.

The active route is not an MCDM/Kraljic service, a Streamlit application, or a
prototype runtime. Mock fixtures remain development-test-only and never become
a local-load fallback, production result, or public approval.

## Cleanup status

The former Class 3 MCDM/Streamlit implementation and meeting prototypes were
removed by the legacy-runtime cleanup. The former file paths are intentionally
not linked because they no longer exist in the working tree. Git history is the
sole recovery mechanism for that historical implementation and its supporting
notes.

Historical material can describe prior MCDM, supply-risk, clinical-impact, or
prototype assumptions, but it is not an executable contract. Use
`shared_docs/structured/` only as historical problem/data context.

## Guardrails

- No runtime may import the removed Class 3 implementation.
- Do not commit Excel, Parquet, SQLite, generated JSON, model results, ZIP,
  wheels, or executables.
- Field-data validation does not make a result production- or public-approved.
- Future public or enterprise services require separately approved contracts,
  access controls, and release criteria.
