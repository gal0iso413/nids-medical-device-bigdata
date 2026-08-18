import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

describe("published Class 1 generation path", () => {
  it("loads canonical insufficient data through current manifest then generation files", async () => {
    const fixture = JSON.parse(readFileSync(resolve(process.cwd(), "../../tests/fixtures/local_artifact_handoff/canonical-fixture.json"), "utf8"));
    const hash = async (value: unknown) => { const bytes = new TextEncoder().encode(JSON.stringify(value)); const buffer = await crypto.subtle.digest("SHA-256", bytes); return Array.from(new Uint8Array(buffer)).map(x => x.toString(16).padStart(2,"0")).join(""); };
    const current = {handoff_schema_version:"1.0.0",generation:"generations/canonical",anchor_month:"202406",selected_entity_id:"synthetic-a",run_status:"insufficient_graph",checksums:{"internal-service.json":await hash(fixture.class1.service),"internal-one-hop-graph.json":await hash(fixture.class1.graph)}};
    vi.stubEnv("VITE_CLASS1_DATA_SOURCE","local"); vi.stubEnv("VITE_CLASS1_HANDOFF_URL","/generated/class1-current.json");
    vi.stubGlobal("fetch", vi.fn((url:string) => { const value = url.endsWith("current.json") ? current : url.endsWith("internal-service.json") ? fixture.class1.service : fixture.class1.graph; const text = JSON.stringify(value); return Promise.resolve({ok:true,text:async()=>text,json:async()=>JSON.parse(text)}); }) as unknown as typeof fetch);
    render(<App />); expect(await screen.findByText(/관계망이 충분하지 않습니다/)).toBeInTheDocument(); expect(document.body.textContent).not.toContain("raw_score");
  });
});
