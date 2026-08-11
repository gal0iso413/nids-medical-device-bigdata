import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";
import { fixtureCatalog } from "../mock/fixtures";

const requiredHeadings = [
  "업체·품목군 비교분석",
  "품목군·품목명 검색",
  "선택 품목",
  "기간 선택",
  "품목별 비교 결과",
  "월별 추세",
  "선택 포트폴리오 요약",
  "관측된 유통 도달 구조",
  "데이터 coverage·결측·억제 안내",
  "버전 정보",
];

describe("Class 3 static shell", () => {
  it("renders the production API-unconnected state as unavailable", () => {
    render(<App initialState={{ kind: "unavailable", message: "서비스 데이터 연결 전" }} />);
    expect(screen.getByRole("status")).toHaveTextContent("서비스 데이터 연결 전");
  });

  it("provides accessible headings for every required shell area", () => {
    render(<App initialState={{ kind: "fixture", fixture: fixtureCatalog.released }} />);

    for (const heading of requiredHeadings) {
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }

    expect(screen.getByLabelText("품목군 검색")).toBeDisabled();
    expect(screen.getByLabelText("품목명 검색")).toBeDisabled();
    expect(screen.getByLabelText("시작 월")).toBeDisabled();
    expect(screen.getByLabelText("종료 월")).toBeDisabled();
  });

  it.each([
    ["loading", "화면 상태를 준비하는 중입니다."],
    ["error", "개발 화면 오류"],
    ["unavailable", "서비스 데이터 연결 전"],
  ] as const)("renders the %s state", (kind, message) => {
    render(<App initialState={{ kind, message }} />);
    expect(screen.getByRole("status")).toHaveTextContent(message);
  });

  it("renders the empty result separately from unavailable", () => {
    render(<App initialState={{ kind: "fixture", fixture: fixtureCatalog.empty }} />);
    expect(screen.getByText("조건에 맞는 결과가 없습니다.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("결과 없음 상태 예시");
  });
});
