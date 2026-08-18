export type DecimalString = string | null;

export interface ApiStatus { service_mode: "local_internal_only"; public_release_policy: "not_approved"; period_start: string; period_end: string; mart_fingerprint: string; }
export interface ApiCatalogItem { item_group_id: string; item_name_id?: string; }
export interface ApiSelection { selection_type: "item_group" | "item_name"; item_group_id: string; item_name_id?: string; }
export interface ApiComparisonView {
  period_start: string;
  period_end: string;
  selections: ApiSelection[];
  product_catalog: Array<Record<string, unknown>>;
  product_month: Array<Record<string, unknown>>;
  item_group_month: Array<Record<string, unknown>>;
  endpoint_composition: Array<Record<string, unknown>>;
  coverage: Array<Record<string, unknown>>;
  selection_concentration: Array<Record<string, unknown>>;
  portfolio_overlap: Record<string, unknown>;
}

const forbidden = ["src_company_id", "dst_company_id", "co:", "hosp:", "raw_score", "entity_hash"];

function object(value: unknown, label: string): Record<string, unknown> { if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} is invalid.`); return value as Record<string, unknown>; }
function string(value: unknown, label: string): string { if (typeof value !== "string") throw new Error(`${label} is invalid.`); return value; }
function optionalString(value: unknown, label: string): string | undefined { return value == null ? undefined : string(value, label); }
function array(value: unknown, label: string): unknown[] { if (!Array.isArray(value)) throw new Error(`${label} is invalid.`); return value; }
function assertSafe(value: unknown): void { const text = JSON.stringify(value).toLowerCase(); if (forbidden.some((token) => text.includes(token))) throw new Error("API response violated the local endpoint privacy boundary."); }
function apiBaseUrl(): string { const base = import.meta.env.VITE_CLASS3_API_BASE_URL ?? "/api"; if (!base.startsWith("/") || base.startsWith("//")) throw new Error("API base URL must be same-origin."); return base.replace(/\/$/, ""); }

export function validateStatus(value: unknown): ApiStatus {
  assertSafe(value); const data = object(value, "status");
  if (data.service_mode !== "local_internal_only" || data.public_release_policy !== "not_approved") throw new Error("API is not in the approved local-internal-only state.");
  return { service_mode: "local_internal_only", public_release_policy: "not_approved", period_start: string(data.period_start, "period_start"), period_end: string(data.period_end, "period_end"), mart_fingerprint: string(data.mart_fingerprint, "mart_fingerprint") };
}

export function validateComparison(value: unknown): ApiComparisonView {
  assertSafe(value); const data = object(value, "comparison");
  const selections: ApiSelection[] = array(data.selections, "selections").map((entry) => { const row = object(entry, "selection"); const type = string(row.selection_type, "selection_type"); if (type !== "item_group" && type !== "item_name") throw new Error("selection type is invalid."); const selectionType: ApiSelection["selection_type"] = type; const group = string(row.item_group_id, "item_group_id"); const name = optionalString(row.item_name_id, "item_name_id"); if ((selectionType === "item_name") !== Boolean(name)) throw new Error("item-name parent scope is invalid."); return { selection_type: selectionType, item_group_id: group, ...(name ? { item_name_id: name } : {}) }; });
  const table = (name: string) => array(data[name], name).map((entry) => object(entry, name));
  const overlap = data.portfolio_overlap == null ? {} : object(data.portfolio_overlap, "portfolio_overlap");
  return {
    period_start: string(data.period_start, "period_start"),
    period_end: string(data.period_end, "period_end"),
    selections,
    product_catalog: table("product_catalog"),
    product_month: table("product_month"),
    item_group_month: table("item_group_month"),
    endpoint_composition: table("endpoint_composition"),
    coverage: table("coverage"),
    selection_concentration: data.selection_concentration == null ? [] : table("selection_concentration"),
    portfolio_overlap: overlap,
  };
}

export class ApiAnalysisAdapter {
  constructor(private readonly baseUrl = apiBaseUrl(), private readonly request: typeof fetch = fetch.bind(globalThis)) {}
  private async json(path: string, init?: RequestInit): Promise<unknown> { const response = await this.request(`${this.baseUrl}${path}`, init); if (!response.ok) throw new Error(`Local API request failed (${response.status}).`); return response.json(); }
  async status(): Promise<ApiStatus> { return validateStatus(await this.json("/v1/status")); }
  async itemGroups(query: string, limit = 20): Promise<ApiCatalogItem[]> { const data = object(await this.json(`/v1/catalog/item-groups?q=${encodeURIComponent(query)}&limit=${limit}`), "catalog"); assertSafe(data); return array(data.items, "items").map((value) => ({ item_group_id: string(object(value, "item").item_group_id, "item_group_id") })); }
  async itemNames(itemGroupId: string, query: string, limit = 20): Promise<ApiCatalogItem[]> { const params = new URLSearchParams({ item_group_id: itemGroupId, q: query, limit: String(limit) }); const data = object(await this.json(`/v1/catalog/item-names?${params}`), "catalog"); assertSafe(data); return array(data.items, "items").map((value) => { const row = object(value, "item"); const group = string(row.item_group_id, "item_group_id"); if (group !== itemGroupId) throw new Error("API returned an item name outside its parent item group."); return { item_group_id: group, item_name_id: string(row.item_name_id, "item_name_id") }; }); }
  async compare(periodStart: string, periodEnd: string, selections: ApiSelection[]): Promise<ApiComparisonView> { return validateComparison(await this.json("/v1/comparisons", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ period_start: periodStart, period_end: periodEnd, selections }) })); }
}
