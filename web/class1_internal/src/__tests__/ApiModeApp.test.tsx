import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import ApiModeApp from "../ApiModeApp";
import { LookupEntityMissingError, type Class1LookupAdapter } from "../apiLookupAdapter";

const status = {
  service_mode: "local_internal_only",
  public_release_policy: "not_approved",
  anchor_month: "202406",
  available_anchor_months: ["202405", "202406"],
  default_anchor_month: "202406",
  window_months: ["202404", "202405", "202406"],
  entity_count: 2,
  edge_count: 1,
  index_fingerprint: "abc",
  trains_on_request: false,
  review_queue: { role_group: "distributor", limit: 10 },
};

const ready = {
  kind: "ready" as const,
  service: {
    analysis_schema_version: "1.0.0",
    run_status: "completed",
    service_results: [{
      entity_id: "a", anchor_month: "202406", window_months: ["202404", "202405", "202406"],
      model: "gadnr", model_version: "1", role_group: "distributor", role_group_sample_size: 10,
      review_priority_percentile: 100, insufficient_sample: false, reason: null,
      graph_summary: { node_count: 2, edge_count: 1, self_loop_count: 0 },
      previous_anchor_diff: {}, prior_nonoverlap_3m_diff: {}, bc_evidence: {},
    }],
  },
  graph: {
    graph_scope: "one_hop" as const, selected_entity_id: "a", anchor_month: "202406",
    window_months: ["202404", "202405", "202406"],
    nodes: [
      { entity_id: "a", selected: true, role_group: "distributor", region: "11", region_missing_or_conflict: false, display_name: "합성유통", name_conflict: false },
      { entity_id: "b", selected: false, role_group: "hospital", region: "26", region_missing_or_conflict: false, display_name: "합성병원", name_conflict: false },
    ],
    edges: [{
      src_company_id: "a", dst_company_id: "b", tx_count: 3, unique_product_count: 1, active_month_count: 1,
      amount_sum_clean: "1", amount_valid_row_count: 1, amount_valid_rate: "1",
      raw_supply_qty_sum: "1", raw_supply_qty_valid_row_count: 1, raw_supply_qty_valid_rate: "1",
      piece_qty_sum: "1", piece_qty_valid_row_count: 1, piece_qty_valid_rate: "1",
    }],
    graph_summary: { selected_node_count: 1, one_hop_counterparty_count: 1, edge_count: 1, self_loop_excluded_count: 0, truncated: false, truncation_reason: null },
  },
};

describe("Class 1 API lookup screen", () => {
  afterEach(() => {
    cleanup();
  });
  it("opens the distributor review queue then a 1-hop on click", async () => {
    const adapter: Class1LookupAdapter = {
      status: async () => status,
      reviewQueue: vi.fn(async () => ({
        anchor_month: "202406",
        window_months: ["202404", "202405", "202406"],
        role_group: "distributor",
        limit: 10,
        eligible_count: 1,
        truncated: false,
        entities: [{
          rank: 1,
          entity_id: "a",
          display_name: "합성유통",
          name_conflict: false,
          role_group: "distributor",
          region: "11",
          review_priority_percentile: 100,
          role_group_sample_size: 10,
        }],
      })),
      search: vi.fn(async () => []),
      lookup: vi.fn(async () => ready),
    };
    render(<ApiModeApp adapter={adapter} status={status} />);
    expect(await screen.findByText("유통업체 검토 우선순위 상위 10곳")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /합성유통/ }));
    expect(await screen.findByText("역할군 백분위 100")).toBeInTheDocument();
    expect(screen.getByText("최초 선택 업체")).toBeInTheDocument();
    expect(screen.getAllByText("합성유통").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/합성병원/).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain("raw_score");
  });

  it("keeps the selected company across anchor months and reports absence", async () => {
    const adapter: Class1LookupAdapter = {
      status: async () => status,
      reviewQueue: vi.fn(async (month) => ({
        anchor_month: month ?? "202406",
        window_months: month === "202405" ? ["202403", "202404", "202405"] : ["202404", "202405", "202406"],
        role_group: "distributor",
        limit: 10,
        eligible_count: 1,
        truncated: false,
        entities: [{
          rank: 1,
          entity_id: month === "202405" ? "b" : "a",
          display_name: month === "202405" ? "다른유통" : "합성유통",
          name_conflict: false,
          role_group: "distributor",
          region: "11",
          review_priority_percentile: 100,
          role_group_sample_size: 10,
        }],
      })),
      search: vi.fn(async () => []),
      lookup: vi.fn(async (_id, month) => {
        if (month === "202405") {
          throw new LookupEntityMissingError("entity missing");
        }
        return ready;
      }),
    };
    render(<ApiModeApp adapter={adapter} status={status} />);
    fireEvent.click(await screen.findByRole("button", { name: /합성유통/ }));
    expect(await screen.findByText("역할군 백분위 100")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("완료 앵커월"), { target: { value: "202405" } });
    expect(await screen.findByText("이 업체는 해당 앵커 창에 없습니다")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /다른유통/ })).toBeInTheDocument();
    expect(adapter.lookup).toHaveBeenCalledWith("a", "202405");
  });

  it("looks up a Korean company name as a secondary path", async () => {
    const adapter: Class1LookupAdapter = {
      status: async () => status,
      reviewQueue: async () => ({
        anchor_month: "202406",
        window_months: ["202404", "202405", "202406"],
        role_group: "distributor",
        limit: 10,
        eligible_count: 0,
        truncated: false,
        entities: [],
      }),
      search: vi.fn(async () => [{
        entity_id: "a",
        display_name: "베타유통",
        name_conflict: false,
        role_group: "distributor",
        region: "11",
      }]),
      lookup: vi.fn(async () => ({
        ...ready,
        graph: {
          ...ready.graph,
          nodes: [
            { ...ready.graph.nodes[0], display_name: "베타유통" },
            ready.graph.nodes[1],
          ],
        },
      })),
    };
    render(<ApiModeApp adapter={adapter} status={status} />);
    expect(await screen.findByText(/특정 업체를 알고 있으면/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("업체명"), { target: { value: "베타유통" } });
    expect(await screen.findByRole("button", { name: /^베타유통/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^베타유통/ }));
    expect(await screen.findByText("역할군 백분위 100")).toBeInTheDocument();
    expect(screen.getAllByText("베타유통").length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain("raw_score");
  });
});
