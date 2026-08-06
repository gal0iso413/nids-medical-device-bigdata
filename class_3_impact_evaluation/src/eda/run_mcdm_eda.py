"""
Retired entrypoint — Class 3 product is now the cohort dashboard.

Use:
  python -m class_3_impact_evaluation.src.eda.run_cohort_pipeline
  streamlit run class_3_impact_evaluation/app.py

Historical MCDM script: class_3_impact_evaluation/archive/run_mcdm_eda.py
"""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "Class 3 MCDM EDA is retired. "
        "Run: python -m class_3_impact_evaluation.src.eda.run_cohort_pipeline",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
