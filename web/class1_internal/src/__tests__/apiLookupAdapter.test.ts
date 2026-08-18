import { describe, expect, it, vi } from "vitest";
import { createClass1LookupAdapter, LookupEntityMissingError, LookupMonthUnavailableError } from "../apiLookupAdapter";

const status = {
  service_mode: "local_internal_only",
  public_release_policy: "not_approved",
  anchor_month: "202406",
  window_months: ["202404", "202405", "202406"],
  entity_count: 2,
  edge_count: 1,
  index_fingerprint: "abc",
  trains_on_request: false,
};
const service = {
  analysis_schema_version: "1.0.0",
  run_status: "completed",
  service_results: [{
    entity_id: "a", anchor_month: "202406", window_months: ["202404", "202405", "202406"],
    model: "gadnr", model_version: "1", role_group: "distributor", role_group_sample_size: 10,
    review_priority_percentile: 50, insufficient_sample: false, reason: null,
    graph_summary: { node_count: 2, edge_count: 1, self_loop_count: 0 },
    previous_anchor_diff: {}, prior_nonoverlap_3m_diff: {}, bc_evidence: {},
  }],
};
const graph = {
  graph_scope: "one_hop", selected_entity_id: "a", anchor_month: "202406",
  window_months: ["202404", "202405", "202406"],
  nodes: [{ entity_id: "a", selected: true, role_group: "distributor", region: "11", region_missing_or_conflict: false }],
  edges: [],
  graph_summary: { selected_node_count: 1, one_hop_counterparty_count: 0, edge_count: 0, self_loop_excluded_count: 0, truncated: false, truncation_reason: null },
};

describe("Class 1 lookup adapter", () => {
  it("loads status and a lookup pair without accepting raw scores", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      const path = String(url);
      const payload = path.includes("/v1/status") ? status : path.includes("/relationships") ? graph : service;
      return { ok: true, status: 200, json: async () => payload };
    }) as unknown as typeof fetch);
    const adapter = createClass1LookupAdapter("/api");
    await expect(adapter.status()).resolves.toMatchObject({ trains_on_request: false, entity_count: 2 });
    const ready = await adapter.lookup("a", "202406");
    expect(ready.graph.selected_entity_id).toBe("a");
    expect(JSON.stringify(ready)).not.toContain("raw_score");
    const urls = vi.mocked(fetch).mock.calls.map((call) => String(call[0]));
    expect(urls.some((item) => item.includes("anchor_month=202406") && item.includes("/v1/entities/a"))).toBe(true);
  });

  it("loads the fixed distributor review queue", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      expect(String(url)).toContain("/v1/review-queue");
      return {
        ok: true,
        status: 200,
        json: async () => ({
          anchor_month: "202406",
          window_months: ["202404", "202405", "202406"],
          role_group: "distributor",
          limit: 10,
          eligible_count: 1,
          truncated: false,
          entities: [{
            rank: 1, entity_id: "a", display_name: "합성유통", name_conflict: false,
            role_group: "distributor", region: "11", review_priority_percentile: 100,
            role_group_sample_size: 12,
          }],
        }),
      };
    }) as unknown as typeof fetch);
    const queue = await createClass1LookupAdapter("/api").reviewQueue();
    expect(queue.entities).toHaveLength(1);
    expect(queue.entities[0]?.display_name).toBe("합성유통");
    expect(JSON.stringify(queue)).not.toContain("raw_score");
  });

  it("loads a bounded Korean name catalog", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      expect(String(url)).toContain("/v1/catalog/entities?");
      expect(String(url)).toContain("q=");
      return {
        ok: true,
        status: 200,
        json: async () => ({
          query: "합성",
          limit: 20,
          match_count: 1,
          truncated: false,
          entities: [{ entity_id: "a", display_name: "합성의료", name_conflict: false, role_group: "distributor", region: "11" }],
        }),
      };
    }) as unknown as typeof fetch);
    await expect(createClass1LookupAdapter("/api").search("합성")).resolves.toEqual([
      { entity_id: "a", display_name: "합성의료", name_conflict: false, role_group: "distributor", region: "11" },
    ]);
  });

  it("rejects lookup payloads that contain raw_score", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true, status: 200, json: async () => ({ ...service, raw_score: 1 }),
    })) as unknown as typeof fetch);
    await expect(createClass1LookupAdapter("/api").lookup("a")).rejects.toThrow(/raw_score/);
  });

  it("maps 404 to a missing entity and 422 missing month to an unavailable month", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (String(url).includes("missing")) {
        return { ok: false, status: 404, json: async () => ({ detail: "entity_id is not in the lookup index" }) };
      }
      return { ok: false, status: 422, json: async () => ({ detail: "anchor_month is not an available lookup partition" }) };
    }) as unknown as typeof fetch);
    await expect(createClass1LookupAdapter("/api").lookup("missing", "202406")).rejects.toBeInstanceOf(LookupEntityMissingError);
    await expect(createClass1LookupAdapter("/api").lookup("a", "202501")).rejects.toBeInstanceOf(LookupMonthUnavailableError);
  });
});
