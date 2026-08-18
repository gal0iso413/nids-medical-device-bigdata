import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ApiModeApp from "../ApiModeApp";
import type { ApiAnalysisAdapter, ApiStatus } from "../dataSource/apiAnalysisAdapter";

const status: ApiStatus = { service_mode: "local_internal_only", public_release_policy: "not_approved", period_start: "202401", period_end: "202402", mart_fingerprint: "safe" };
const result = {
  period_start: "202401",
  period_end: "202402",
  selections: [{ selection_type: "item_group" as const, item_group_id: "Group A" }],
  product_catalog: [
    { product_id: "p3:1", item_group_id: "Group A", item_name_id: "Name A" },
    { product_id: "p3:2", item_group_id: "Group A", item_name_id: "Name B" },
  ],
  product_month: [
    { month: "202401", product_id: "p3:1", tx_count: 3, amount_sum_clean: "10.000000", raw_supply_qty_sum: "2.000000", piece_qty_sum: "3.000000" },
    { month: "202402", product_id: "p3:1", tx_count: 1, amount_sum_clean: "2.500000", raw_supply_qty_sum: "1.000000", piece_qty_sum: "1.000000" },
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
  ],
  coverage: [{ month: "202401", amount_sum_clean: "12.500000", aggregate_observation_count: 1 }],
  selection_concentration: [{ selection_type: "item_group", item_group_id: "Group A", month: "202402", supplier_hhi_tx: "0.500000" }],
  portfolio_overlap: { supplier_union_count: 2, receiver_union_count: 10, pairs: [] },
};

function adapter(overrides: Partial<ApiAnalysisAdapter> = {}): ApiAnalysisAdapter {
  return { itemGroups: vi.fn(async () => Array.from({ length: 20 }, (_, index) => ({ item_group_id: `Group ${index}` }))), itemNames: vi.fn(async (group: string) => [{ item_group_id: group, item_name_id: "Name A" }]), compare: vi.fn(async () => result), ...overrides } as unknown as ApiAnalysisAdapter;
}

describe("Class 2 API mode UI", () => {
  it("clamps a long mart period to 36 months so comparison stays runnable", async () => {
    render(<ApiModeApp adapter={adapter()} status={{ ...status, period_start: "202008", period_end: "202605" }} />);
    expect(screen.getByLabelText("시작 월")).toHaveValue("2023-06");
    expect(screen.getByLabelText("종료 월")).toHaveValue("2026-05");
    await screen.findByRole("button", { name: /Group 0/ });
    fireEvent.click(screen.getByRole("button", { name: /Group 0/ }));
    expect(screen.getByRole("button", { name: "비교 실행" })).toBeEnabled();
  });
  it("shows five preview cards until search is focused, then a 20-item scroll list", async () => {
    render(<ApiModeApp adapter={adapter()} status={status} />);
    await screen.findByRole("button", { name: /Group 0/ });
    expect(screen.getByRole("button", { name: /Group 4/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Group 5/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("품목군 검색 결과")).not.toBeInTheDocument();
    fireEvent.focus(screen.getByLabelText("품목군 검색"));
    expect(screen.getByRole("button", { name: /Group 19/ })).toBeInTheDocument();
    expect(screen.getByLabelText("품목군 검색 결과")).toHaveClass("is-scroll");
  });

  it("shows local policy-pending state, bounded parent-scoped choices, and preserves Decimal text", async () => {
    const client = adapter(); render(<ApiModeApp adapter={client} status={status} />);
    expect(screen.getByRole("status")).toHaveTextContent("현재 화면 상태");
    expect(screen.getByRole("status")).toHaveTextContent("공개 정책은 적용되지 않았습니다");
    await screen.findByRole("button", { name: /Group 0/ });
    fireEvent.click(screen.getByRole("button", { name: /Group 0/ }));
    await screen.findByRole("button", { name: /Name A/ });
    fireEvent.click(screen.getByRole("button", { name: /Name A/ }));
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await waitFor(() => expect(client.compare).toHaveBeenCalled());
    expect(screen.getByRole("heading", { name: /품목군 · Group A/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "선택한 품목 비교" })).toBeInTheDocument();
    expect(screen.getByText("기간 초 대비")).toBeInTheDocument();
    expect(screen.getByText("-3건")).toBeInTheDocument();
    expect(screen.getByText(/2024-01 4건 → 2024-02 1건/)).toBeInTheDocument();
    expect(screen.getByText("월 거래 건수 중앙값")).toBeInTheDocument();
    expect(screen.getByText("2.5")).toBeInTheDocument();
    expect(screen.getByText(/의료기관 60%/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "선택 포트폴리오 요약" })).toBeInTheDocument();
    expect(screen.getByText("공급 집중도 (최근 월)")).toBeInTheDocument();
    expect(screen.getAllByText("5,000").length).toBeGreaterThan(0);
    expect(screen.getByText("수령 역할 (최근 월, 거래 건수)")).toBeInTheDocument();
    expect(screen.getByText("서울")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "선택 조건 요약" })).toBeInTheDocument();
    expect(screen.getByText("선택 품목 누락 월")).toBeInTheDocument();
    expect(screen.getByText("마트에 없는 월")).toBeInTheDocument();
    expect(screen.getByText("공개 억제")).toBeInTheDocument();
    expect(screen.getByText("미적용")).toBeInTheDocument();
    expect(screen.queryByText("12.500000")).not.toBeInTheDocument();
    expect(screen.queryByText("12.5")).not.toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(1);
    expect(screen.getByRole("img", { name: "선택 품목의 월별 거래 건수 추세" })).toBeInTheDocument();
    expect(screen.queryByText("p3:1")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "상위 품목·구성 보기" }));
    expect(screen.getAllByText("12.5").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Name A").length).toBeGreaterThan(0);
    expect(screen.getByText("Name B")).toBeInTheDocument();
  });

  it("enforces ten selections, a 36-month period, and explicit API errors without fallback", async () => {
    const client = adapter({ compare: vi.fn(async () => { throw new Error("offline"); }) });
    render(<ApiModeApp adapter={client} status={{ ...status, period_start: "202001", period_end: "202401" }} />);
    await screen.findByRole("button", { name: /Group 0/ });
    fireEvent.focus(screen.getByLabelText("품목군 검색"));
    await screen.findByRole("button", { name: "품목군 Group 10" });
    for (let index = 0; index < 11; index += 1) {
      fireEvent.click(screen.getByRole("button", { name: `품목군 Group ${index}` }));
    }
    expect(screen.getByText("선택 품목 (10/10)")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("시작 월"), { target: { value: "2020-01" } });
    expect(screen.getByRole("button", { name: "비교 실행" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("종료 월"), { target: { value: "2022-12" } });
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("비교 요청이 실패했거나 로컬 API가 거부했습니다."));
  });

  it("renders an explicit empty state from a successful API comparison", async () => {
    const client = adapter({ compare: vi.fn(async () => ({ ...result, product_month: [], item_group_month: [] })) });
    render(<ApiModeApp adapter={client} status={status} />);
    await screen.findByRole("button", { name: /Group 0/ });
    fireEvent.click(screen.getByRole("button", { name: /Group 0/ }));
    fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
    await screen.findByText("조건에 맞는 결과가 없습니다.");
    expect(screen.getByRole("heading", { name: "선택 조건 요약" })).toBeInTheDocument();
  });
});
