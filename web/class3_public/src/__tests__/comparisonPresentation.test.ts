import { describe, expect, it } from "vitest";
import type { ApiComparisonView } from "../dataSource/apiAnalysisAdapter";
import {
  displayDecimal,
  displayDeltaShort,
  displayHhi,
  displayMissingMonths,
  displayMonthSpan,
  displayPeriodChange,
  filterProducts,
  monthsInPeriod,
  presentComparison,
} from "../comparison/presentation";

const view: ApiComparisonView = {
  period_start: "202401",
  period_end: "202402",
  selections: [{ selection_type: "item_group", item_group_id: "Group A" }],
  product_catalog: [
    { product_id: "p3:1", item_group_id: "Group A", item_name_id: "Name A" },
    { product_id: "p3:2", item_group_id: "Group A", item_name_id: "Name B" },
    { product_id: "p3:9", item_group_id: "Group B", item_name_id: "Other" },
  ],
  product_month: [
    { month: "202401", product_id: "p3:1", tx_count: 3, amount_sum_clean: "10.000000" },
    { month: "202402", product_id: "p3:1", tx_count: 1, amount_sum_clean: "2.500000" },
    { month: "202401", product_id: "p3:2", tx_count: 1, amount_sum_clean: "1.000000" },
  ],
  item_group_month: [
    { month: "202401", item_group_id: "Group A", tx_count: 4, amount_sum_clean: "11.000000", raw_supply_qty_sum: "2.000000", piece_qty_sum: "3.000000", amount_valid_row_count: 2, raw_supply_qty_valid_row_count: 4, supplier_count_distinct: 2, receiver_count_distinct: 5 },
    { month: "202402", item_group_id: "Group A", tx_count: 1, amount_sum_clean: "1.500000", raw_supply_qty_sum: "1.000000", piece_qty_sum: "1.000000", amount_valid_row_count: 1, raw_supply_qty_valid_row_count: 1, supplier_count_distinct: 1, receiver_count_distinct: 10 },
  ],
  endpoint_composition: [
    { month: "202402", product_scope: "item_group", product_scope_id: "Group A", endpoint: "receiver", dimension: "type", dimension_value: "의료기관", entity_count_distinct: 6, tx_count: 1 },
    { month: "202402", product_scope: "item_group", product_scope_id: "Group A", endpoint: "receiver", dimension: "type", dimension_value: "판매(임대)업", entity_count_distinct: 3, tx_count: 0 },
    { month: "202402", product_scope: "item_group", product_scope_id: "Group A", endpoint: "receiver", dimension: "region", dimension_value: "서울", entity_count_distinct: 9 },
    { month: "202402", product_scope: "item_group", product_scope_id: "Group A", endpoint: "receiver", dimension: "region", dimension_value: "경기", entity_count_distinct: 4 },
    { month: "202401", product_scope: "item_group", product_scope_id: "Group A", endpoint: "receiver", dimension: "region", dimension_value: "부산", entity_count_distinct: 99 },
  ],
  coverage: [
    { month: "202401", amount_sum_clean: "11.000000", aggregate_observation_count: 4 },
    { month: "202402", amount_sum_clean: "1.500000", aggregate_observation_count: 1 },
  ],
  selection_concentration: [
    { selection_type: "item_group", item_group_id: "Group A", month: "202401", supplier_hhi_tx: "0.520000" },
    { selection_type: "item_group", item_group_id: "Group A", month: "202402", supplier_hhi_tx: "0.500000" },
  ],
  portfolio_overlap: { supplier_union_count: 2, receiver_union_count: 10, pairs: [] },
};

describe("Class 3 comparison presentation", () => {
  it("collapses month and product rows into one selection summary", () => {
    const presented = presentComparison(view);
    expect(presented.summaries).toHaveLength(1);
    expect(presented.summaries[0]).toMatchObject({
      label: "Group A",
      month_count: 2,
      median_tx_count: 2.5,
      tx_count: 5,
      amount_sum_clean: "12.500000",
      latest_supplier_count: 1,
      latest_receiver_count: 10,
      amount_valid_rate: 0.6,
      qty_valid_rate: 1,
      region_names: ["서울", "경기"],
    });
    expect(presented.summaries[0]?.receiver_mix.map((item) => item.label)).toEqual(["의료기관", "유통", "미확인"]);
    expect(presented.summaries[0]?.receiver_mix_tx.map((item) => item.label)).toEqual(["의료기관"]);
    expect(presented.summaries[0]?.supplier_hhi_tx).toBe("0.500000");
    expect(presented.summaries[0]?.period_change).toMatchObject({
      start_month: "202401",
      end_month: "202402",
      tx_from: 4,
      tx_to: 1,
      supplier_from: 2,
      supplier_to: 1,
      receiver_from: 5,
      receiver_to: 10,
    });
    expect(presented.portfolio.shares[0]?.tx_share).toBe(1);
    expect(presented.portfolio.supplier_union_count).toBe(2);
    expect(presented.summaries[0]?.products.map((item) => item.item_name_id)).toEqual(["Name A", "Name B"]);
    expect(presented.query).toMatchObject({
      period_start: "202401",
      period_end: "202402",
      included_months: ["202401", "202402"],
      missing_months: [],
    });
    expect(presented.coverage.included_months).toEqual(["202401", "202402"]);
    expect(presented.coverage.missing_months).toEqual([]);
  });

  it("splits requested months into included and missing months", () => {
    const presented = presentComparison({
      ...view,
      period_end: "202403",
      coverage: view.coverage,
    });
    expect(presented.query.missing_months).toEqual(["202403"]);
    expect(presented.coverage.missing_months).toEqual(["202403"]);
    expect(displayMonthSpan(presented.query.included_months)).toBe("2024-01 ~ 2024-02 (2개월)");
    expect(displayMissingMonths(presented.query.missing_months)).toBe("2024-03");
  });

  it("formats stored Decimal strings for display without changing the source value", () => {
    expect(displayDecimal("39697456761.000000")).toBe("39,697,456,761");
    expect(displayDecimal("12.500000")).toBe("12.5");
    expect(displayDecimal("1.000000")).toBe("1");
    expect(displayDecimal(null)).toBe("없음");
    expect(displayHhi("0.500000")).toBe("5,000");
    expect(displayHhi(null)).toBe("없음");
    expect(displayDeltaShort(4, 1, "건")).toBe("-3건");
    expect(displayDeltaShort(1, 1, "건")).toBe("변화 없음");
    expect(displayPeriodChange("202401", "202402", 4, 1, "건")).toBe("2024-01 4건 → 2024-02 1건 · 3건 감소");
    expect(monthsInPeriod("202411", "202502")).toEqual(["202411", "202412", "202501", "202502"]);
  });

  it("keeps item-name selections on their parent group and ranks only matching products", () => {
    const presented = presentComparison({
      ...view,
      selections: [{ selection_type: "item_name", item_group_id: "Group A", item_name_id: "Name A" }],
    });
    expect(presented.summaries[0]?.label).toBe("Group A / Name A");
    expect(presented.summaries[0]?.tx_count).toBe(4);
    expect(presented.summaries[0]?.median_tx_count).toBe(2);
    expect(presented.summaries[0]?.products).toHaveLength(1);
    expect(presented.summaries[0]?.latest_supplier_count).toBeNull();
  });

  it("limits default product rows and searches inside the selection", () => {
    const products = Array.from({ length: 8 }, (_, index) => ({
      product_id: `p3:${index}`,
      item_name_id: index === 6 ? "Needle" : `Item ${index}`,
      tx_count: 8 - index,
      amount_sum_clean: "1.000000",
    }));
    expect(filterProducts(products, "").map((item) => item.item_name_id)).toEqual([
      "Item 0", "Item 1", "Item 2", "Item 3", "Item 4",
    ]);
    expect(filterProducts(products, "need").map((item) => item.item_name_id)).toEqual(["Needle"]);
  });
});
