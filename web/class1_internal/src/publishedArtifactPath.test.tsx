import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

describe("published Class 1 local artifact path", () => {
  it("loads the canonical score-free insufficient artifact from generated paths", async () => {
    const fixture = JSON.parse(readFileSync(resolve(process.cwd(), "../../tests/fixtures/local_artifact_handoff/canonical-fixture.json"), "utf8"));
    vi.stubEnv("VITE_CLASS1_DATA_SOURCE", "local");
    vi.stubEnv("VITE_CLASS1_SERVICE_URL", "/generated/internal-service.json");
    vi.stubEnv("VITE_CLASS1_GRAPH_URL", "/generated/internal-one-hop-graph.json");
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve({ ok: true, json: () => Promise.resolve(url === "/generated/internal-service.json" ? fixture.class1.service : fixture.class1.graph) })) as unknown as typeof fetch);
    render(<App />);
    expect(await screen.findByText(/관계망이 충분하지 않습니다/)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("raw_score");
  });
});
