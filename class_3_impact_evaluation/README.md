# Class 3 — Anonymous Cohort Dashboard

Internal Streamlit wizard: 업종 · 권역 · 품목군 → 거시/진단 → 품목군 지도 → multi 품목명.

No firm search, no entity risk / GNN scores. MCDM/Kraljic UI is retired
(`archive/`).

## Pipeline

```bash
# Prefer Class 1 Parquet if already materialized
python -m class_3_impact_evaluation.src.eda.run_cohort_pipeline

streamlit run class_3_impact_evaluation/app.py
```

## Config hooks

`config/cohort_config.json` — includes deferred `my_company_mode_enabled: false`.

## Spec

See `shared_docs/structured/class_3_evaluation_spec.md`.
