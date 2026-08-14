import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "../App";
import { loadLocalClass3Analysis } from "../dataSource/localAnalysisAdapter";

describe("canonical Class 3 local artifact handoff", () => {
  it("loads the tracked synthetic artifact through the local adapter and renders catalog coverage", async () => {
    const fixture = JSON.parse(readFileSync(resolve(process.cwd(), "../../tests/fixtures/local_artifact_handoff/canonical-fixture.json"), "utf8"));
    const analysis = await loadLocalClass3Analysis("/canonical", async () => new Response(JSON.stringify(fixture.class3), { status: 200 }));
    render(<App initialState={{ kind: "local_analysis", analysis }} />);
    const search = screen.getByRole("searchbox", { name: "품목군 또는 품목명 검색" });
    fireEvent.focus(search);
    fireEvent.click(within(screen.getByRole("list", { name: "품목 검색 결과" })).getByRole("button", { name: /SYNTHETIC_GROUP/ }));
    expect(screen.getAllByText("SYNTHETIC_GROUP")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "데이터 coverage·결측·억제 안내" })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("raw_score");
  });
});
