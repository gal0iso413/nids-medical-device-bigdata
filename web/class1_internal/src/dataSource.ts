import type { GraphPayload, ServicePayload } from "./contracts";
export type LoadState = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; service: ServicePayload; graph: GraphPayload };
const object = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const string = (v: unknown): v is string => typeof v === "string";
export function validatePayloads(service: unknown, graph: unknown): { service: ServicePayload; graph: GraphPayload } {
  if (!object(service) || !string(service.analysis_schema_version) || !string(service.run_status) || !Array.isArray(service.service_results)) throw new Error("internal-service payload contract is invalid");
  if (!object(graph) || graph.graph_scope !== "one_hop" || !string(graph.selected_entity_id) || !string(graph.anchor_month) || !Array.isArray(graph.window_months) || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges) || !object(graph.graph_summary)) throw new Error("internal one-hop graph payload contract is invalid");
  const selected = service.service_results.find((row) => object(row) && row.entity_id === graph.selected_entity_id);
  if (!selected) throw new Error("service and graph selected entity IDs do not match");
  if (JSON.stringify(service).includes("raw_score") || JSON.stringify(graph).includes("raw_score")) throw new Error("raw_score is forbidden in internal web payloads");
  return { service: service as unknown as ServicePayload, graph: graph as unknown as GraphPayload };
}
export async function loadLocal(): Promise<LoadState> {
  if (import.meta.env.VITE_CLASS1_DATA_SOURCE !== "local") return { kind: "error", message: "로컬 분석 데이터 소스가 설정되지 않았습니다." };
  const serviceUrl = import.meta.env.VITE_CLASS1_SERVICE_URL; const graphUrl = import.meta.env.VITE_CLASS1_GRAPH_URL;
  if (!serviceUrl || !graphUrl) return { kind: "error", message: "VITE_CLASS1_SERVICE_URL과 VITE_CLASS1_GRAPH_URL이 필요합니다." };
  try { const [service, graph] = await Promise.all([fetch(serviceUrl).then(async r => { if (!r.ok) throw new Error("service load failed"); return r.json(); }), fetch(graphUrl).then(async r => { if (!r.ok) throw new Error("graph load failed"); return r.json(); })]); const valid = validatePayloads(service, graph); return { kind: "ready", ...valid }; } catch { return { kind: "error", message: "로컬 분석 JSON을 검증하거나 불러오지 못했습니다. mock fallback은 사용하지 않습니다." }; }
}
