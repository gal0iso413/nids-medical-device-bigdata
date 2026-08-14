import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";
import { loadDevelopmentMock } from "../mock/developmentAdapter";

function setup(name = "released") { render(<App initialState={{ kind: "fixture", fixture: loadDevelopmentMock(name) }} />); }
function search(value: string) { const input = screen.getByRole("searchbox", { name: "품목군 또는 품목명 검색" }); fireEvent.focus(input); fireEvent.change(input, { target: { value } }); return within(screen.getByRole("list", { name: "품목 검색 결과" })); }

describe("Class 3 synthetic mock interaction regression", () => {
  it("searches item groups", () => { setup(); expect(search("ITEM_GROUP").getByText("SYNTHETIC_ITEM_GROUP_ALPHA")).toBeInTheDocument(); });
  it("searches item names", () => { setup(); expect(search("ITEM_NAME").getByText("SYNTHETIC_ITEM_NAME_BETA")).toBeInTheDocument(); });
  it("removes a selection", () => { setup(); fireEvent.click(screen.getByRole("button", { name: "SYNTHETIC_ITEM_GROUP_ALPHA 선택 제거" })); expect(screen.queryByRole("button", { name: "SYNTHETIC_ITEM_GROUP_ALPHA 선택 제거" })).not.toBeInTheDocument(); });
  it("adds a removed selection", () => { setup(); fireEvent.click(screen.getByRole("button", { name: "SYNTHETIC_ITEM_GROUP_ALPHA 선택 제거" })); fireEvent.click(search("ITEM_GROUP").getByRole("button", { name: /SYNTHETIC_ITEM_GROUP_ALPHA/ })); expect(screen.getByRole("button", { name: "SYNTHETIC_ITEM_GROUP_ALPHA 선택 제거" })).toBeInTheDocument(); });
  it("prevents duplicate selection", () => { setup(); const item = search("ITEM_GROUP").getByRole("button", { name: /SYNTHETIC_ITEM_GROUP_ALPHA/ }); expect(item).toBeDisabled(); });
  it("blocks an invalid period", () => { setup(); fireEvent.change(screen.getByLabelText("시작 월"), { target: { value: "2099-04" } }); fireEvent.change(screen.getByLabelText("종료 월"), { target: { value: "2099-03" } }); expect(screen.getByRole("alert")).toHaveTextContent("시작 월은 종료 월보다 늦을 수 없습니다."); expect(screen.getByRole("button", { name: "기간 적용" })).toBeDisabled(); });
  it("applies a valid period", () => { setup(); fireEvent.change(screen.getByLabelText("시작 월"), { target: { value: "2099-02" } }); fireEvent.change(screen.getByLabelText("종료 월"), { target: { value: "2099-03" } }); fireEvent.click(screen.getByRole("button", { name: "기간 적용" })); expect(screen.getByText("화면 비교 범위: 2099-02 ~ 2099-03")).toBeInTheDocument(); });
  it("shows only selected mock results", () => { setup(); fireEvent.click(screen.getByRole("button", { name: "SYNTHETIC_ITEM_GROUP_ALPHA 선택 제거" })); const results = screen.getByRole("heading", { name: "품목별 비교 결과" }).closest("section")!; expect(within(results).queryByText("synthetic:item-group:alpha")).not.toBeInTheDocument(); expect(within(results).getByText("synthetic:item-name:beta")).toBeInTheDocument(); });
  it("keeps released mock labels", () => { setup(); expect(screen.getAllByText("SYNTHETIC_ACTIVITY_DISPLAY")).toHaveLength(2); expect(screen.getAllByText("SYNTHETIC_PER_ITEM_QUANTITY_DISPLAY")).toHaveLength(2); });
  it("renders fixture coverage state", () => { setup(); expect(screen.getAllByText(/상태:/).length).toBeGreaterThan(0); });
});
