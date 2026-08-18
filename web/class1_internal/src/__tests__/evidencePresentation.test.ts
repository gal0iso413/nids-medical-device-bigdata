import { describe, expect, it } from "vitest";
import { presentBcEvidence, presentPeriodDiffs } from "../evidencePresentation";

describe("Class 1 evidence presentation", () => {
  it("turns BC fields into Korean path-through copy without English keys", () => {
    const presented = presentBcEvidence({
      gateway_share: "0.2",
      reachable_source_target_pairs: 10,
      reachable_target_count: 4,
      weak_component_size: 20,
      mode: "exact",
      insufficient_evidence: false,
      bc_insufficient_sample: false,
      bc_percentile: 90.04,
      bc_rank: 3,
      bc_role_group_sample_size: 12,
    });
    expect(presented.headline).toBe("역할군 백분위 90");
    expect(presented.rows.map((row) => row.label).join(" ")).not.toMatch(/gateway|mode|component|reachable/i);
    expect(presented.rows.find((row) => row.label === "관측 경로에서 차지하는 비중")?.value).toBe("20%");
    expect(presented.rows.find((row) => row.label === "계산 범위")?.value).toContain("전체 경로");
  });

  it("summarizes relationship and volume diffs as counts, not identifiers", () => {
    const presented = presentPeriodDiffs(
      {
        current_months: ["202404", "202405", "202406"],
        comparison_months: ["202403", "202404", "202405"],
        new_counterparty_ids: ["alpha", "beta"],
        retained_counterparty_ids: ["kept"],
        lost_counterparty_ids: [],
      },
      {
        current_months: ["202404", "202405", "202406"],
        comparison_months: ["202401", "202402", "202403"],
        tx_count_change: -3,
        counterparty_count_change: 2,
        product_count_change: 0,
        amount_change: "8.25",
      },
    );
    expect(presented.headline).toBe("신규 거래처 2곳 · 소실 0곳");
    expect(presented.rows.find((row) => row.label.includes("거래 건수"))?.value).toBe("-3건");
    expect(presented.rows.find((row) => row.label === "품목 수 변화")?.value).toBe("변화 없음");
    expect(JSON.stringify(presented)).not.toContain("alpha");
  });
});
