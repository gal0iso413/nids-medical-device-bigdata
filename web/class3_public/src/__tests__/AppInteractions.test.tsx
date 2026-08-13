import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";
import { loadDevelopmentMock } from "../mock/developmentAdapter";

const releasedFixture = loadDevelopmentMock("released");

function renderReleased() {
  render(<App initialState={{ kind: "fixture", fixture: releasedFixture }} />);
}

function removeSelection(label: string) {
  fireEvent.click(screen.getByRole("button", { name: `${label} 선택 제거` }));
}

describe("Class 3 comparison interactions", () => {
  it("filters item groups and item names from one searchbox", () => {
    renderReleased();
    const searchbox = screen.getByRole("searchbox", {
      name: "품목군 또는 품목명 검색",
    });

    fireEvent.focus(searchbox);
    expect(screen.getByRole("list", { name: "품목 검색 결과" })).toBeInTheDocument();

    fireEvent.change(searchbox, { target: { value: "item_group" } });
    const groupResults = within(screen.getByRole("list", { name: "품목 검색 결과" }));
    expect(groupResults.getByText("SYNTHETIC_ITEM_GROUP_ALPHA")).toBeInTheDocument();
    expect(groupResults.queryByText("SYNTHETIC_ITEM_NAME_BETA")).not.toBeInTheDocument();

    fireEvent.change(searchbox, { target: { value: "품목명" } });
    const nameResults = within(screen.getByRole("list", { name: "품목 검색 결과" }));
    expect(nameResults.queryByText("SYNTHETIC_ITEM_GROUP_ALPHA")).not.toBeInTheDocument();
    expect(nameResults.getByText("SYNTHETIC_ITEM_NAME_BETA")).toBeInTheDocument();
    expect(screen.getByText("검색 결과 1개")).toBeInTheDocument();
  });

  it("supports multiple selection, removal, and duplicate prevention", () => {
    renderReleased();
    removeSelection("SYNTHETIC_ITEM_GROUP_ALPHA");
    removeSelection("SYNTHETIC_ITEM_NAME_BETA");
    expect(screen.getAllByText(/선택된 품목이 없습니다/)).toHaveLength(2);

    const searchbox = screen.getByRole("searchbox", {
      name: "품목군 또는 품목명 검색",
    });
    fireEvent.focus(searchbox);
    const results = within(screen.getByRole("list", { name: "품목 검색 결과" }));
    const groupButton = results.getByRole("button", { name: /SYNTHETIC_ITEM_GROUP_ALPHA/ });
    expect(groupButton.tagName).toBe("BUTTON");
    groupButton.focus();
    expect(document.activeElement).toBe(groupButton);
    fireEvent.click(groupButton);
    expect(groupButton).toBeDisabled();
    expect(screen.getAllByRole("button", { name: "SYNTHETIC_ITEM_GROUP_ALPHA 선택 제거" })).toHaveLength(1);

    const nameButton = results.getByRole("button", { name: /SYNTHETIC_ITEM_NAME_BETA/ });
    fireEvent.click(nameButton);
    expect(screen.getAllByRole("button", { name: /선택 제거/ })).toHaveLength(2);
  });

  it("blocks an invalid period and applies only a valid local display range", () => {
    renderReleased();
    const startMonth = screen.getByLabelText("시작 월");
    const endMonth = screen.getByLabelText("종료 월");
    const applyButton = screen.getByRole("button", { name: "기간 적용" });

    fireEvent.change(startMonth, { target: { value: "2099-04" } });
    fireEvent.change(endMonth, { target: { value: "2099-03" } });
    expect(screen.getByRole("alert")).toHaveTextContent("시작 월은 종료 월보다 늦을 수 없습니다.");
    expect(startMonth).toHaveAttribute("aria-invalid", "true");
    expect(applyButton).toBeDisabled();

    fireEvent.change(startMonth, { target: { value: "2099-02" } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(applyButton).toBeEnabled();
    fireEvent.click(applyButton);
    expect(screen.getByText(/화면 비교 범위: 2099-02 ~ 2099-03/)).toBeInTheDocument();
    expect(screen.getByText(/mock 분석값은 재계산하지 않습니다/)).toBeInTheDocument();
  });

  it("shows only selected per-item results and released labels", () => {
    renderReleased();
    removeSelection("SYNTHETIC_ITEM_GROUP_ALPHA");
    const resultSection = screen.getByRole("heading", { name: "품목별 비교 결과" }).closest("section");
    expect(resultSection).not.toBeNull();
    const results = within(resultSection!);
    expect(results.queryByText("synthetic:item-group:alpha")).not.toBeInTheDocument();
    expect(results.getByText("synthetic:item-name:beta")).toBeInTheDocument();
    expect(results.getByText("SYNTHETIC_ACTIVITY_DISPLAY")).toBeInTheDocument();
    expect(results.getByText("SYNTHETIC_PER_ITEM_QUANTITY_DISPLAY")).toBeInTheDocument();
    expect(results.getByText("SYNTHETIC_MONTHLY_TREND_DISPLAY")).toBeInTheDocument();

    const trendSection = screen.getByRole("heading", { name: "월별 추세" }).closest("section");
    expect(within(trendSection!).queryByText("synthetic:item-group:alpha")).not.toBeInTheDocument();
    expect(within(trendSection!).getByText("synthetic:item-name:beta")).toBeInTheDocument();

    const portfolioSection = screen.getByRole("heading", { name: "선택 포트폴리오 요약" }).closest("section");
    expect(within(portfolioSection!).queryByText("synthetic:item-group:alpha")).not.toBeInTheDocument();
    expect(within(portfolioSection!).getByText("synthetic:item-name:beta")).toBeInTheDocument();
  });

  it.each([
    ["suppressed_small_cell", "소수 집단 억제 상태 예시"],
    ["suppressed_dominance", "우세도 억제 상태 예시"],
    ["suppressed_differencing", "차분 위험 억제 상태 예시"],
    ["insufficient_coverage", "데이터 범위 부족 상태 예시"],
    ["not_available", "제공 전 상태 예시"],
  ] as const)("keeps %s results non-released and text-identifiable", (fixtureName, label) => {
    const fixture = loadDevelopmentMock(fixtureName);
    render(<App initialState={{ kind: "fixture", fixture }} />);
    expect(screen.getByRole("status")).toHaveTextContent(label);
    expect(screen.queryByText("SYNTHETIC_ACTIVITY_DISPLAY")).not.toBeInTheDocument();
    const trendSection = screen.getByRole("heading", { name: "월별 추세" }).closest("section");
    expect(within(trendSection!).getAllByText(new RegExp(label))).not.toHaveLength(0);
  });

  it("renders coverage missing as explicit text", () => {
    const missingFixture = structuredClone(releasedFixture);
    const firstField = missingFixture.coverage.field_states[0];
    if (!firstField) {
      throw new Error("Released fixture must include a coverage field.");
    }
    firstField.state = "missing";
    firstField.notice = "Synthetic missing coverage marker.";

    render(<App initialState={{ kind: "fixture", fixture: missingFixture }} />);
    const coverageSection = screen.getByRole("heading", {
      name: "데이터 coverage·결측·억제 안내",
    }).closest("section");
    expect(within(coverageSection!).getByText("상태: missing")).toBeInTheDocument();
    expect(within(coverageSection!).getByText("Synthetic missing coverage marker.")).toBeInTheDocument();
  });
});
