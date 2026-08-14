import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";
import { loadDevelopmentMock } from "../mock/developmentAdapter";

describe("Class 3 synthetic mock shell regression", () => {
  it("keeps the approved shell headings", () => {
    render(<App initialState={{ kind: "fixture", fixture: loadDevelopmentMock("released") }} />);
    for (const heading of ["업체·품목군 비교분석", "품목군/품목명 검색", "선택 품목", "기간 선택", "품목별 비교 결과", "월별 추세", "데이터 coverage·결측·억제 안내", "버전 정보"]) expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
  });
  it("keeps the unavailable state", () => { render(<App initialState={{ kind: "unavailable", message: "unavailable" }} />); expect(screen.getByRole("status")).toHaveTextContent("unavailable"); });
  it("keeps the loading state", () => { render(<App initialState={{ kind: "loading", message: "loading" }} />); expect(screen.getByRole("status")).toHaveTextContent("loading"); });
  it("keeps the error state", () => { render(<App initialState={{ kind: "error", message: "error" }} />); expect(screen.getByRole("status")).toHaveTextContent("error"); });
  it("labels group and name selections distinctly", () => { render(<App initialState={{ kind: "fixture", fixture: loadDevelopmentMock("released") }} />); expect(screen.getByText("SYNTHETIC_ITEM_GROUP_ALPHA").closest("li")).toHaveTextContent("품목군"); expect(screen.getByText("SYNTHETIC_ITEM_NAME_BETA").closest("li")).toHaveTextContent("품목명"); });
  it("keeps an empty fixture distinct from unavailable", () => { render(<App initialState={{ kind: "fixture", fixture: loadDevelopmentMock("empty") }} />); expect(screen.getByRole("status")).toHaveTextContent("결과 없음 상태"); expect(screen.getByText("적용 기간에 표시할 선택 품목 결과가 없습니다.")).toBeInTheDocument(); });
  it.each([
    ["released", "공개 가능한 합성 mock 상태"],
    ["suppressed_small_cell", "소수 집단 억제 상태"],
    ["suppressed_dominance", "우세값 억제 상태"],
    ["suppressed_differencing", "차분 위험 억제 상태"],
    ["insufficient_coverage", "데이터 coverage 부족 상태"],
    ["not_available", "제공 불가 상태"],
  ] as const)("keeps the %s mock status explicit", (name, status) => { render(<App initialState={{ kind: "fixture", fixture: loadDevelopmentMock(name) }} />); expect(screen.getByRole("status")).toHaveTextContent(status); });
  it("keeps the development-only marker", () => { render(<App initialState={{ kind: "fixture", fixture: loadDevelopmentMock("released") }} />); expect(screen.getByText("합성 개발 데이터 또는 서비스 데이터 미연결")).toBeInTheDocument(); });
});
