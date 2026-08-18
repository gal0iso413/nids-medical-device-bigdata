"""Compatibility entrypoint for the standalone Class 2 serving-mart batch job."""

from data_pipeline.analysis.class2_serving_mart import main


if __name__ == "__main__":
    raise SystemExit(main())
