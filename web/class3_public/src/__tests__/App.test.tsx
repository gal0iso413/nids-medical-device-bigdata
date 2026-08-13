import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";
import { loadDevelopmentMock } from "../mock/developmentAdapter";

const releasedFixture = loadDevelopmentMock("released");
const emptyFixture = loadDevelopmentMock("empty");

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
    render(<App initialState={{ kind: "fixture", fixture: releasedFixture }} />);

    const skipLink = screen.getByRole("link", { name: "본문 바로가기" });
    expect(skipLink).toHaveAttribute("href", "#main-content");
    expect(document.getElementById("main-content")).toHaveAttribute("tabindex", "-1");

    for (const heading of requiredHeadings) {
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }

    const searchInputs = screen.getAllByRole("searchbox");
    expect(searchInputs).toHaveLength(1);
    expect(screen.getByLabelText("품목군 또는 품목명 검색")).toBeEnabled();
    expect(screen.getByPlaceholderText("품목군·품목명을 한 번에 검색하는 영역")).toBeEnabled();
    expect(screen.getByLabelText("시작 월")).toBeEnabled();
    expect(screen.getByLabelText("종료 월")).toBeEnabled();
  });

  it("translates item contract types into public Korean labels", () => {
    render(<App initialState={{ kind: "fixture", fixture: releasedFixture }} />);

    expect(screen.getByText("SYNTHETIC_ITEM_GROUP_ALPHA").closest("li")).toHaveTextContent(
      "품목군",
    );
    expect(screen.getByText("SYNTHETIC_ITEM_NAME_BETA").closest("li")).toHaveTextContent(
      "품목명",
    );
    expect(screen.getAllByRole("heading", { name: "품목군" })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { name: "품목명" })).toHaveLength(1);
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
    render(<App initialState={{ kind: "fixture", fixture: emptyFixture }} />);
    expect(screen.getByText("조건에 맞는 결과가 없습니다.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("결과 없음 상태 예시");
    expect(emptyFixture.per_item_results).toHaveLength(0);
  });

  it.each([
    ["released", "공개 가능 상태 예시"],
    ["suppressed_small_cell", "소수 집단 억제 상태 예시"],
    ["suppressed_dominance", "우세도 억제 상태 예시"],
    ["suppressed_differencing", "차분 위험 억제 상태 예시"],
    ["insufficient_coverage", "데이터 범위 부족 상태 예시"],
    ["not_available", "제공 전 상태 예시"],
  ] as const)("identifies the %s fixture state with text", (fixtureName, label) => {
    const fixture = loadDevelopmentMock(fixtureName);
    render(<App initialState={{ kind: "fixture", fixture }} />);
    expect(screen.getByRole("status")).toHaveTextContent(label);
  });
});
