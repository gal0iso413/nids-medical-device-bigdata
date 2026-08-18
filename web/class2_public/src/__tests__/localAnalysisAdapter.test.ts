// @vitest-environment node
import { describe, expect, it } from "vitest";
import { validateClass2AnalysisPayload } from "../dataSource/localAnalysisAdapter";
import { syntheticClass2AnalysisPayload } from "../test/class2AnalysisPayload";

describe("Class 2 local analysis payload validation", () => {
  it("accepts a PR #15 shaped payload without converting Decimal strings", () => {
    const value = validateClass2AnalysisPayload(syntheticClass2AnalysisPayload);
    expect(value.selection_month_metrics[0]?.amount_sum_clean).toBe("123456789.123456");
  });

  it("rejects an unsupported schema version", () => {
    expect(() => validateClass2AnalysisPayload({ ...syntheticClass2AnalysisPayload, analysis_schema_version: "9.0.0" })).toThrow("Unsupported analysis_schema_version");
  });

  it("rejects a missing required array", () => {
    const { selection_month_metrics: _metrics, ...invalid } = syntheticClass2AnalysisPayload;
    expect(() => validateClass2AnalysisPayload(invalid)).toThrow("selection_month_metrics must be an array");
  });
});
