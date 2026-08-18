import { validatePayloads, type LoadState } from "./dataSource";

export interface ApiStatus {
  service_mode: string;
  public_release_policy: string;
  anchor_month: string;
  window_months: string[];
  entity_count: number;
  edge_count: number;
  index_fingerprint: string;
  trains_on_request: boolean;
  review_queue?: { role_group: string; limit: number };
}

export interface ReviewQueueItem {
  rank: number;
  entity_id: string;
  display_name: string | null;
  name_conflict: boolean;
  role_group: string;
  region: string | null;
  review_priority_percentile: number;
  role_group_sample_size: number;
}

export interface ReviewQueue {
  anchor_month: string;
  window_months: string[];
  role_group: string;
  limit: number;
  eligible_count: number;
  truncated: boolean;
  entities: ReviewQueueItem[];
}

export interface CatalogHit {
  entity_id: string;
  display_name: string | null;
  name_conflict: boolean;
  role_group: string;
  region: string | null;
}

export interface Class1LookupAdapter {
  status(): Promise<ApiStatus>;
  reviewQueue(): Promise<ReviewQueue>;
  search(query: string, limit?: number): Promise<CatalogHit[]>;
  lookup(entityId: string): Promise<Extract<LoadState, { kind: "ready" }>>;
}

const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

async function readJson(url: string, label: string): Promise<unknown> {
  const response = await fetch(url);
  if (response.status === 404) throw new Error(`${label} not found`);
  if (!response.ok) throw new Error(`${label} load failed`);
  return response.json();
}

export function createClass1LookupAdapter(baseUrl = "/api"): Class1LookupAdapter {
  const root = baseUrl.replace(/\/$/, "");
  return {
    async status() {
      const payload = await readJson(`${root}/v1/status`, "status");
      if (!object(payload) || payload.service_mode !== "local_internal_only" || payload.trains_on_request !== false) {
        throw new Error("Class 1 lookup API status contract is invalid");
      }
      return payload as unknown as ApiStatus;
    },
    async reviewQueue() {
      const payload = await readJson(`${root}/v1/review-queue`, "review-queue");
      if (!object(payload) || !Array.isArray(payload.entities) || payload.role_group !== "distributor" || payload.limit !== 10) {
        throw new Error("Class 1 review-queue contract is invalid");
      }
      if (JSON.stringify(payload).includes("raw_score")) {
        throw new Error("raw_score is forbidden in lookup API payloads");
      }
      return payload as unknown as ReviewQueue;
    },
    async search(query: string, limit = 20) {
      const params = new URLSearchParams({ q: query.trim(), limit: String(limit) });
      const payload = await readJson(`${root}/v1/catalog/entities?${params.toString()}`, "catalog");
      if (!object(payload) || !Array.isArray(payload.entities)) {
        throw new Error("Class 1 catalog contract is invalid");
      }
      return payload.entities as CatalogHit[];
    },
    async lookup(entityId: string) {
      const encoded = encodeURIComponent(entityId.trim());
      const [service, graph] = await Promise.all([
        readJson(`${root}/v1/entities/${encoded}`, "review"),
        readJson(`${root}/v1/entities/${encoded}/relationships`, "relationships"),
      ]);
      if (JSON.stringify(service).includes("raw_score") || JSON.stringify(graph).includes("raw_score")) {
        throw new Error("raw_score is forbidden in lookup API payloads");
      }
      return { kind: "ready" as const, ...validatePayloads(service, graph) };
    },
  };
}
