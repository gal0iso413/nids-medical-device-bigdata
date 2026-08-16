import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ApiModeApp from "../ApiModeApp";
import type { ApiAnalysisAdapter, ApiStatus } from "../dataSource/apiAnalysisAdapter";

const status: ApiStatus = { service_mode: "local_internal_only", public_release_policy: "not_approved", period_start: "202401", period_end: "202402", mart_fingerprint: "safe" };
const result = { period_start: "202401", period_end: "202402", selections: [{ selection_type: "item_group" as const, item_group_id: "Group A" }], product_catalog: [], product_month: [{ month: "202401", product_id: "p3:1", tx_count: 1, amount_sum_clean: "12.500000", raw_supply_qty_sum: "2.000000", piece_qty_sum: "3.000000" }], item_group_month: [], endpoint_composition: [], coverage: [] };

function adapter(overrides: Partial<ApiAnalysisAdapter> = {}): ApiAnalysisAdapter {
  return { itemGroups: vi.fn(async () => Array.from({ length: 11 }, (_, index) => ({ item_group_id: `Group ${index}` }))), itemNames: vi.fn(async (group: string) => [{ item_group_id: group, item_name_id: "Name A" }]), compare: vi.fn(async () => result), ...overrides } as unknown as ApiAnalysisAdapter;
}

describe("Class 3 API mode UI", () => {
  it("shows local policy-pending state, bounded parent-scoped choices, and preserves Decimal text", async () => {
    const client = adapter(); render(<ApiModeApp adapter={client} status={status} />);
    expect(screen.getByRole("status")).toHaveTextContent("local_internal_only");
    expect(screen.getByText("public_release_policy: not_approved")).toBeInTheDocument();
    await screen.findByRole("button", { name: "Group 0" });
    fireEvent.click(screen.getByRole("button", { name: "Group 0" }));
    await screen.findByRole("button", { name: "Name A" });
    fireEvent.click(screen.getByRole("button", { name: "Name A" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply comparison" }));
    await waitFor(() => expect(client.compare).toHaveBeenCalled());
    expect(screen.getByText("12.500000")).toBeInTheDocument();
  });

  it("enforces ten selections, a 36-month period, and explicit API errors without fallback", async () => {
    const client = adapter({ compare: vi.fn(async () => { throw new Error("offline"); }) });
    render(<ApiModeApp adapter={client} status={{ ...status, period_start: "202001", period_end: "202401" }} />);
    await screen.findByRole("button", { name: "Group 0" });
    for (let index = 0; index < 11; index += 1) fireEvent.click(screen.getByRole("button", { name: `Group ${index}` }));
    expect(screen.getByText("Selections (10/10)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply comparison" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("End"), { target: { value: "2022-12" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply comparison" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/failed or was rejected/i));
  });

  it("renders an explicit empty state from a successful API comparison", async () => {
    const client = adapter({ compare: vi.fn(async () => ({ ...result, product_month: [], item_group_month: [] })) });
    render(<ApiModeApp adapter={client} status={status} />);
    await screen.findByRole("button", { name: "Group 0" });
    fireEvent.click(screen.getByRole("button", { name: "Group 0" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply comparison" }));
    await screen.findByText("No aggregate observations are available for the selected local query.");
  });
});
