"""Compatibility entrypoint for the standalone Class 3 serving-mart batch job."""

from data_pipeline.analysis.class3_serving_mart import main


if __name__ == "__main__":
    raise SystemExit(main())
