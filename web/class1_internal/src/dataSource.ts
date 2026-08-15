import type { GraphPayload, ServicePayload } from "./contracts";
export type LoadState = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; service: ServicePayload; graph: GraphPayload };
const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const string = (v: unknown): v is string => typeof v === "string";
const HANDOFF_SCHEMA_VERSION = "1.0.0";
export function validatePayloads(service: unknown, graph: unknown): { service: ServicePayload; graph: GraphPayload } {
  if (!object(service) || !string(service.analysis_schema_version) || !string(service.run_status) || !Array.isArray(service.service_results)) throw new Error("internal-service payload contract is invalid");
  if (service.run_status !== "completed" && service.run_status !== "insufficient_graph") throw new Error("unsupported local run_status");
  if (!object(graph) || graph.graph_scope !== "one_hop" || !string(graph.selected_entity_id) || !string(graph.anchor_month) || !Array.isArray(graph.window_months) || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges) || !object(graph.graph_summary)) throw new Error("internal one-hop graph payload contract is invalid");
  const selectedNodes = graph.nodes.filter((node) => object(node) && node.selected === true);
  if (selectedNodes.length !== 1 || selectedNodes[0].entity_id !== graph.selected_entity_id) throw new Error("graph selected node contract is invalid");
  if (graph.edges.some((edge) => !object(edge) || (edge.src_company_id !== graph.selected_entity_id && edge.dst_company_id !== graph.selected_entity_id))) throw new Error("graph contains a non-incident edge");
  if (service.run_status === "completed") { const selected = service.service_results.find((row) => object(row) && row.entity_id === graph.selected_entity_id); if (!selected || selected.anchor_month !== graph.anchor_month || JSON.stringify(selected.window_months) !== JSON.stringify(graph.window_months)) throw new Error("service and graph selected entity IDs or analysis window do not match"); }
  else if (service.service_results.length !== 0) throw new Error("insufficient graph service results must be empty");
  if (JSON.stringify(service).includes("raw_score") || JSON.stringify(graph).includes("raw_score")) throw new Error("raw_score is forbidden in internal web payloads");
  return { service: service as unknown as ServicePayload, graph: graph as unknown as GraphPayload };
}
const digest = async (value: unknown) => { const bytes = new TextEncoder().encode(JSON.stringify(value)); const hash = await crypto.subtle.digest("SHA-256", bytes); return Array.from(new Uint8Array(hash)).map(x => x.toString(16).padStart(2, "0")).join(""); };
export async function loadLocal(): Promise<LoadState> {
  if (import.meta.env.VITE_CLASS1_DATA_SOURCE !== "local") return { kind: "error", message: "로컬 분석 데이터 소스가 설정되지 않았습니다." };
  const currentUrl = import.meta.env.VITE_CLASS1_HANDOFF_URL || "/generated/class1-current.json";
  try {
    const current = await fetch(currentUrl).then(async r => { if (!r.ok) throw new Error("current manifest load failed"); return r.json(); });
    if (!object(current) || current.handoff_schema_version !== HANDOFF_SCHEMA_VERSION || !string(current.generation) || !string(current.anchor_month) || !string(current.selected_entity_id) || !string(current.run_status) || !object(current.checksums)) throw new Error("current handoff manifest contract is invalid");
    const base = currentUrl.slice(0, currentUrl.lastIndexOf("/") + 1); const generation = `${base}${current.generation}/`;
    const [service, graph] = await Promise.all([fetch(`${generation}internal-service.json`).then(async r => { if (!r.ok) throw new Error("service load failed"); return r.json(); }), fetch(`${generation}internal-one-hop-graph.json`).then(async r => { if (!r.ok) throw new Error("graph load failed"); return r.json(); })]);
    if (await digest(service) !== current.checksums["internal-service.json"] || await digest(graph) !== current.checksums["internal-one-hop-graph.json"]) throw new Error("generation checksum mismatch");
    const valid = validatePayloads(service, graph); if (valid.service.run_status !== current.run_status || valid.graph.anchor_month !== current.anchor_month || valid.graph.selected_entity_id !== current.selected_entity_id) throw new Error("generation identity mismatch");
    return { kind: "ready", ...valid };
  } catch { return { kind: "error", message: "로컬 분석 handoff manifest 또는 generation JSON을 검증하지 못했습니다. mock fallback은 사용하지 않습니다." }; }
}
