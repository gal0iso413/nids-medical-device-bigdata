import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";
import { syntheticClass3AnalysisPayload } from "../test/class3AnalysisPayload";

function renderLocal() { render(<App initialState={{ kind: "local_analysis", analysis: syntheticClass3AnalysisPayload }} />); }
function choose(label: string) {
  const search = screen.getByRole("searchbox", { name: "품목군 또는 품목명 검색" });
  fireEvent.focus(search);
  fireEvent.click(within(screen.getByRole("list", { name: "품목 검색 결과" })).getAllByRole("button", { name: new RegExp(label) })[0]!);
}

describe("Class 3 local analysis UI", () => {
  it("labels local analysis as policy-unapplied rather than released", () => {
    renderLocal();
    expect(screen.getByRole("status")).toHaveTextContent("로컬 분석 데이터 · 공개 정책 미적용");
    expect(screen.queryByText("released")).not.toBeInTheDocument();
  });

  it("searches the complete catalog and preserves item-name parent scopes", () => {
    renderLocal();
    const search = screen.getByRole("searchbox", { name: "품목군 또는 품목명 검색" });
    fireEvent.focus(search);
    fireEvent.change(search, { target: { value: "TEST_NAME" } });
    const results = within(screen.getByRole("list", { name: "품목 검색 결과" }));
    expect(results.getAllByText("TEST_NAME")).toHaveLength(2);
    expect(results.getByText("상위 품목군: TEST_GROUP")).toBeInTheDocument();
    expect(results.getByText("상위 품목군: TEST_OTHER_GROUP")).toBeInTheDocument();
  });

  it("supports multi-selection and removal without merging equal item names", () => {
    renderLocal();
    choose("TEST_NAME");
    const search = screen.getByRole("searchbox", { name: "품목군 또는 품목명 검색" });
    fireEvent.change(search, { target: { value: "TEST_OTHER_GROUP" } });
    fireEvent.click(within(screen.getByRole("list", { name: "품목 검색 결과" })).getByRole("button", { name: /TEST_OTHER_GROUP/ }));
    expect(screen.getAllByRole("button", { name: "TEST_NAME 선택 제거" })).toHaveLength(2);
    fireEvent.click(screen.getAllByRole("button", { name: "TEST_NAME 선택 제거" })[0]!);
    expect(screen.getAllByRole("button", { name: "TEST_NAME 선택 제거" })).toHaveLength(1);
  });

  it("filters metrics by applied period and keeps Decimal strings unchanged", () => {
    renderLocal(); choose("TEST_GROUP");
    expect(screen.getByText("123456789.123456")).toBeInTheDocument();
    const end = screen.getByLabelText("종료 월");
    fireEvent.change(end, { target: { value: "2024-01" } });
    fireEvent.click(screen.getByRole("button", { name: "기간 적용" }));
    expect(screen.getByText("202401 · 품목군")).toBeInTheDocument();
    expect(screen.queryByText("202402 · 품목명")).not.toBeInTheDocument();
  });

  it("does not display results for an unselected catalog item", () => {
    renderLocal();
    expect(screen.queryByText("123456789.123456")).not.toBeInTheDocument();
    expect(screen.getByText("선택된 품목이 없습니다. 검색 결과에서 품목을 선택해 주세요.")).toBeInTheDocument();
  });

  it("shows missing months, coverage, quality flags, and endpoint observation scope", () => {
    renderLocal(); choose("TEST_GROUP");
    expect(screen.getByText("누락 월: 202402")).toBeInTheDocument();
    expect(screen.getByText("금액 valid rate: 1.000000")).toBeInTheDocument();
    expect(screen.getByText(/최종 의료기관 추적을 의미하지 않습니다/)).toBeInTheDocument();
    expect(screen.getByText(/supplier_type_conflict/)).toBeInTheDocument();
  });

  it("retains the existing synthetic mock state", async () => {
    const { loadDevelopmentMock } = await import("../mock/developmentAdapter");
    render(<App initialState={{ kind: "fixture", fixture: loadDevelopmentMock("released") }} />);
    expect(screen.getByRole("status")).toHaveTextContent("공개 가능 상태 예시");
    expect(screen.getByText("SYNTHETIC_ITEM_GROUP_ALPHA")).toBeInTheDocument();
  });
});
