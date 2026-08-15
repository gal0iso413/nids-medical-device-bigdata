import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import { validatePayloads } from "./dataSource";

const graph = { graph_scope: "one_hop", selected_entity_id: "a", anchor_month: "202406", window_months: ["202404","202405","202406"], nodes: [{entity_id:"a",selected:true,role_group:"distributor",region:"11",region_missing_or_conflict:false}], edges: [], graph_summary:{selected_node_count:1,one_hop_counterparty_count:0,edge_count:0,self_loop_excluded_count:0,truncated:false,truncation_reason:null} };
const insufficient = { analysis_schema_version: "1.0.0", run_status: "insufficient_graph", service_results: [] };
async function sha(value: unknown) { const bytes = new TextEncoder().encode(JSON.stringify(value)); const hash = await crypto.subtle.digest("SHA-256", bytes); return Array.from(new Uint8Array(hash)).map(x => x.toString(16).padStart(2,"0")).join(""); }
async function local(service = insufficient, oneHop = graph) { const current = { handoff_schema_version:"1.0.0", generation:"generations/test", anchor_month:"202406", selected_entity_id:"a", run_status:service.run_status, checksums:{"internal-service.json":await sha(service),"internal-one-hop-graph.json":await sha(oneHop)} }; vi.stubEnv("VITE_CLASS1_DATA_SOURCE", "local"); vi.stubEnv("VITE_CLASS1_HANDOFF_URL", "/generated/class1-current.json"); vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve({ok:true,json:()=>Promise.resolve(url.endsWith("class1-current.json") ? current : url.endsWith("internal-service.json") ? service : oneHop)})) as unknown as typeof fetch); }

describe("Class 1 local monitor", () => {
  it("validates matching local payloads and rejects raw scores", () => { expect(validatePayloads(insufficient, graph).graph.selected_entity_id).toBe("a"); expect(() => validatePayloads({...insufficient, raw_score:1}, graph)).toThrow(/raw_score/); });
  it("renders a score-free insufficient graph generation", async () => { await local(); render(<App />); expect(await screen.findByText(/관계망이 충분하지 않습니다/)).toBeInTheDocument(); expect(document.body.textContent).not.toContain("raw_score"); });
  it("shows an error when the current marker is unavailable", async () => { vi.stubEnv("VITE_CLASS1_DATA_SOURCE", "local"); vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ok:false,json:()=>Promise.resolve({})})) as unknown as typeof fetch); render(<App />); expect(await screen.findByText(/표시할 수 없습니다/)).toBeInTheDocument(); });
  it("rejects unsupported statuses", () => { expect(() => validatePayloads({...insufficient,run_status:"unknown"},graph)).toThrow(/unsupported/); });
  it("shows an error when generation checksums disagree", async () => { await local(); vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve({ok:true,json:()=>Promise.resolve(url.endsWith("class1-current.json") ? {handoff_schema_version:"1.0.0",generation:"generations/test",anchor_month:"202406",selected_entity_id:"a",run_status:"insufficient_graph",checksums:{"internal-service.json":"0","internal-one-hop-graph.json":"0"}} : url.endsWith("internal-service.json") ? insufficient : graph)})) as unknown as typeof fetch); render(<App />); expect(await screen.findByText(/표시할 수 없습니다/)).toBeInTheDocument(); });
  it("requires exactly one selected graph node", () => { expect(() => validatePayloads(insufficient,{...graph,nodes:[]})).toThrow(/selected node/); });
});
