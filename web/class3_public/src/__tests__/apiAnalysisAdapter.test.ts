import { describe, expect, it, vi } from "vitest";
import { ApiAnalysisAdapter, validateComparison } from "../dataSource/apiAnalysisAdapter";

const status = { service_mode: "local_internal_only", public_release_policy: "not_approved", period_start: "202401", period_end: "202402", mart_fingerprint: "safe-fingerprint" };
const comparison = { period_start: "202401", period_end: "202402", selections: [{ selection_type: "item_name" as const, item_group_id: "Group A", item_name_id: "Item A" }], product_catalog: [{ product_id: "p3:1", item_group_id: "Group A", item_name_id: "Item A" }], product_month: [{ month: "202401", product_id: "p3:1", amount_sum_clean: "12.500000", raw_supply_qty_sum: "2.000000", piece_qty_sum: "3.000000", tx_count: 1 }], item_group_month: [], endpoint_composition: [{ month: "202401", product_scope: "product", product_scope_id: "p3:1", endpoint: "supplier", dimension: "type", dimension_value: "manufacturer", entity_count_distinct: 1, tx_count: 1 }], coverage: [{ month: "202401", amount_sum_clean: "12.500000", aggregate_observation_count: 1 }], selection_concentration: [], portfolio_overlap: { supplier_union_count: 1, receiver_union_count: 1, pairs: [] } };

describe("local Class 3 API adapter", () => {
  it("runs status, bounded catalog, parent-scoped names, and comparison without numeric Decimal coercion", async () => {
    const request = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/status")) return new Response(JSON.stringify(status));
      if (url.includes("item-groups")) return new Response(JSON.stringify({ items: [{ item_group_id: "Group A" }] }));
      if (url.includes("item-names")) { expect(url).toContain("item_group_id=Group+A"); return new Response(JSON.stringify({ items: [{ item_group_id: "Group A", item_name_id: "Item A" }] })); }
      expect(init?.method).toBe("POST"); expect(JSON.parse(String(init?.body))).toEqual({ period_start: "202401", period_end: "202402", selections: comparison.selections }); return new Response(JSON.stringify(comparison));
    });
    const adapter = new ApiAnalysisAdapter("/api", request as typeof fetch);
    expect(await adapter.status()).toEqual(status);
    expect(await adapter.itemGroups("group", 20)).toEqual([{ item_group_id: "Group A" }]);
    expect(await adapter.itemNames("Group A", "item", 20)).toEqual([{ item_group_id: "Group A", item_name_id: "Item A" }]);
    const result = await adapter.compare("202401", "202402", comparison.selections);
    expect(result.product_month[0]?.amount_sum_clean).toBe("12.500000");
  });

  it("accepts item-group selections that omit or null item_name_id", () => {
    const payload = { ...comparison, selections: [{ selection_type: "item_group", item_group_id: "Group A", item_name_id: null }] };
    expect(validateComparison(payload).selections).toEqual([{ selection_type: "item_group", item_group_id: "Group A" }]);
  });

  it("blocks raw endpoint identifiers and parent-scope violations before display", async () => {
    expect(() => validateComparison({ ...comparison, endpoint_composition: [{ src_company_id: "co:secret" }] })).toThrow(/privacy/i);
    const request = vi.fn(async () => new Response(JSON.stringify({ items: [{ item_group_id: "Wrong Group", item_name_id: "Item A" }] })));
    await expect(new ApiAnalysisAdapter("/api", request as typeof fetch).itemNames("Group A", "", 20)).rejects.toThrow(/outside/i);
  });
});
