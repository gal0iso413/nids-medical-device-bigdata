import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import { validatePayloads } from "./dataSource";

const graph = { graph_scope: "one_hop", selected_entity_id: "a", anchor_month: "202406", window_months: ["202404","202405","202406"], nodes: [{entity_id:"a",selected:true,role_group:"distributor",region:"11",region_missing_or_conflict:false}], edges: [], graph_summary:{selected_node_count:1,one_hop_counterparty_count:0,edge_count:0,self_loop_excluded_count:0,truncated:false,truncation_reason:null} };
const insufficient = { analysis_schema_version: "1.0.0", run_status: "insufficient_graph", service_results: [] };
async function sha(value: unknown) { const bytes = new TextEncoder().encode(JSON.stringify(value)); const hash = await crypto.subtle.digest("SHA-256", bytes); return Array.from(new Uint8Array(hash)).map(x => x.toString(16).padStart(2,"0")).join(""); }
function jsonResponse(value: unknown) { const text = JSON.stringify(value); return Promise.resolve({ ok: true, text: async () => text, json: async () => JSON.parse(text) }); }
async function local(service: { run_status: string } = insufficient, oneHop: unknown = graph) { const current = { handoff_schema_version:"1.0.0", generation:"generations/test", anchor_month:"202406", selected_entity_id:"a", run_status:service.run_status, checksums:{"internal-service.json":await sha(service),"internal-one-hop-graph.json":await sha(oneHop)} }; vi.stubEnv("VITE_CLASS1_DATA_SOURCE", "local"); vi.stubEnv("VITE_CLASS1_HANDOFF_URL", "/generated/class1-current.json"); vi.stubGlobal("fetch", vi.fn((url: string) => jsonResponse(url.endsWith("class1-current.json") ? current : url.endsWith("internal-service.json") ? service : oneHop)) as unknown as typeof fetch); }

describe("Class 1 local monitor", () => {
  it("validates matching local payloads and rejects raw scores", () => { expect(validatePayloads(insufficient, graph).graph.selected_entity_id).toBe("a"); expect(() => validatePayloads({...insufficient, raw_score:1}, graph)).toThrow(/raw_score/); });
  it("renders a score-free insufficient graph generation", async () => { await local(); render(<App />); expect(await screen.findByText(/관계망이 충분하지 않습니다/)).toBeInTheDocument(); expect(document.body.textContent).not.toContain("raw_score"); });
  it("shows an error when the current marker is unavailable", async () => { vi.stubEnv("VITE_CLASS1_DATA_SOURCE", "local"); vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ok:false,json:()=>Promise.resolve({})})) as unknown as typeof fetch); render(<App />); expect(await screen.findByText(/표시할 수 없습니다/)).toBeInTheDocument(); });
  it("rejects unsupported statuses", () => { expect(() => validatePayloads({...insufficient,run_status:"unknown"},graph)).toThrow(/unsupported/); });
  it("shows an error when generation checksums disagree", async () => { await local(); vi.stubGlobal("fetch", vi.fn((url: string) => jsonResponse(url.endsWith("class1-current.json") ? {handoff_schema_version:"1.0.0",generation:"generations/test",anchor_month:"202406",selected_entity_id:"a",run_status:"insufficient_graph",checksums:{"internal-service.json":"0","internal-one-hop-graph.json":"0"}} : url.endsWith("internal-service.json") ? insufficient : graph)) as unknown as typeof fetch); render(<App />); expect(await screen.findByText(/표시할 수 없습니다/)).toBeInTheDocument(); });
  it("requires exactly one selected graph node", () => { expect(() => validatePayloads(insufficient,{...graph,nodes:[]})).toThrow(/selected node/); });
  it("renders one-hop lanes and review priority for a completed generation", async () => {
    const completedGraph = {
      ...graph,
      nodes: [
        {entity_id:"a",selected:true,role_group:"multi_role",region:"11",region_missing_or_conflict:false},
        {entity_id:"in-1",selected:false,role_group:"manufacturer",region:"11",region_missing_or_conflict:false},
        ...Array.from({length:12}, (_, i) => ({entity_id:`out-${i+1}`,selected:false,role_group:"hospital",region:"11",region_missing_or_conflict:false})),
      ],
      edges: [
        {src_company_id:"in-1",dst_company_id:"a",tx_count:9,unique_product_count:1,active_month_count:1,amount_sum_clean:"1",amount_valid_row_count:1,amount_valid_rate:"1",raw_supply_qty_sum:"1",raw_supply_qty_valid_row_count:1,raw_supply_qty_valid_rate:"1",piece_qty_sum:"1",piece_qty_valid_row_count:1,piece_qty_valid_rate:"1"},
        ...Array.from({length:12}, (_, i) => ({src_company_id:"a",dst_company_id:`out-${i+1}`,tx_count:12-i,unique_product_count:1,active_month_count:1,amount_sum_clean:"1",amount_valid_row_count:1,amount_valid_rate:"1",raw_supply_qty_sum:"1",raw_supply_qty_valid_row_count:1,raw_supply_qty_valid_rate:"1",piece_qty_sum:"1",piece_qty_valid_row_count:1,piece_qty_valid_rate:"1"})),
      ],
      graph_summary:{selected_node_count:1,one_hop_counterparty_count:13,edge_count:13,self_loop_excluded_count:0,truncated:false,truncation_reason:null},
    };
    const completed = { analysis_schema_version:"1.0.0", run_status:"completed", service_results:[{entity_id:"a",anchor_month:"202406",window_months:["202404","202405","202406"],model:"gadnr",model_version:"1",role_group:"multi_role",role_group_sample_size:10,review_priority_percentile:100,insufficient_sample:false,reason:null,graph_summary:{node_count:14,edge_count:13,self_loop_count:0},previous_anchor_diff:{current_months:["202404","202405","202406"],comparison_months:["202403","202404","202405"],new_counterparty_ids:["in-1"],retained_counterparty_ids:[],lost_counterparty_ids:["out-old"]},prior_nonoverlap_3m_diff:{current_months:["202404","202405","202406"],comparison_months:["202401","202402","202403"],tx_count_change:4,counterparty_count_change:-1,product_count_change:0,amount_change:"12.5"},bc_evidence:{gateway_share:"0.25",reachable_source_target_pairs:8,reachable_target_count:3,weak_component_size:14,mode:"exact",insufficient_evidence:false,bc_insufficient_sample:false,bc_percentile:87.5,bc_rank:2,bc_role_group_sample_size:10}}] };
    await local(completed, completedGraph);
    render(<App />);
    expect(await screen.findByText("검토 우선순위")).toBeInTheDocument();
    expect(screen.getByText("역할군 백분위 100")).toBeInTheDocument();
    expect(screen.getByText("경로 통과 보조지표")).toBeInTheDocument();
    expect(screen.getByText("역할군 백분위 87.5")).toBeInTheDocument();
    expect(screen.getByText("관측 경로에서 차지하는 비중")).toBeInTheDocument();
    expect(screen.getByText("25%")).toBeInTheDocument();
    expect(screen.getByText("거래 관계·규모 변화")).toBeInTheDocument();
    expect(screen.getByText(/신규 거래처 1곳/)).toBeInTheDocument();
    expect(screen.getByText("+4건")).toBeInTheDocument();
    expect(screen.getByText("변화 없음")).toBeInTheDocument();
    const headings = screen.getAllByRole("heading").map((node) => node.textContent);
    expect(headings.indexOf("경로 통과 보조지표")).toBeLessThan(headings.indexOf("선택 업체 중심 1-hop 관계망"));
    expect(headings.indexOf("거래 관계·규모 변화")).toBeLessThan(headings.indexOf("선택 업체 중심 1-hop 관계망"));
    expect(screen.getByText("공급 업체")).toBeInTheDocument();
    expect(screen.getByText("최초 선택 업체")).toBeInTheDocument();
    expect(screen.getByText("공급받은 업체")).toBeInTheDocument();
    expect(screen.getByText("기타 2개")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("raw_score");
    expect(document.body.textContent).not.toContain("gateway share");
    expect(document.body.textContent).not.toContain("BC 보조지표");
    expect(document.body.textContent).not.toContain("out-old");
    expect(document.body.textContent).not.toMatch(/co:/);
  });
});
