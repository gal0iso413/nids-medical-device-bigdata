import type { Class3AnalysisPayload } from "../contracts/class3Analysis";
import type { Class3MockFixture } from "../contracts/class3Mock";
import type { ApiAnalysisAdapter, ApiStatus } from "./apiAnalysisAdapter";

export interface RuntimeEnvironment { mode: string; requestedSource?: string; requestedFixture?: string; localAnalysisUrl?: string; }
export type Class3PageState =
  | { kind: "loading"; message: string }
  | { kind: "error"; message: string }
  | { kind: "unavailable"; message: string }
  | { kind: "fixture"; fixture: Class3MockFixture }
  | { kind: "local_analysis"; analysis: Class3AnalysisPayload }
  | { kind: "api"; adapter: ApiAnalysisAdapter; status: ApiStatus };
export type DevelopmentMockLoader = (fixtureName: string) => Promise<Class3MockFixture>;
export type LocalAnalysisLoader = (url: string) => Promise<Class3AnalysisPayload>;
export type ApiLoader = () => Promise<{ adapter: ApiAnalysisAdapter; status: ApiStatus }>;

export function selectDataSource(environment: RuntimeEnvironment): "development_mock" | "local_analysis" | "api" | "unavailable" {
  if (environment.requestedSource === "api") return "api";
  if (environment.requestedSource === "local") return "local_analysis";
  if (environment.mode === "development" && environment.requestedSource === "mock") return "development_mock";
  return "unavailable";
}

export async function resolveClass3PageState(environment: RuntimeEnvironment, loadMock: DevelopmentMockLoader, loadLocal: LocalAnalysisLoader, loadApi?: ApiLoader): Promise<Class3PageState> {
  const source = selectDataSource(environment);
  if (source === "unavailable") return { kind: "unavailable", message: "서비스 데이터가 연결되지 않았습니다." };
  if (source === "local_analysis") {
    try { return { kind: "local_analysis", analysis: await loadLocal(environment.localAnalysisUrl ?? "/generated/class3-analysis.json") }; }
    catch (error) { return { kind: "error", message: `로컬 분석 데이터를 불러오지 못했습니다: ${error instanceof Error ? error.message : "unknown error"}` }; }
  }
  if (source === "api") {
    try { if (!loadApi) throw new Error("API loader is unavailable."); return { kind: "api", ...(await loadApi()) }; }
    catch { return { kind: "error", message: "Local API status check failed. No mock or local-JSON fallback was used." }; }
  }
  try { return { kind: "fixture", fixture: await loadMock(environment.requestedFixture ?? "released") }; }
  catch { return { kind: "error", message: "개발 mock fixture를 불러오지 못했습니다." }; }
}

export async function resolveCurrentClass3PageState(): Promise<Class3PageState> {
  const environment: RuntimeEnvironment = {
    mode: import.meta.env.DEV ? "development" : "production",
    requestedSource: import.meta.env.VITE_CLASS3_DATA_SOURCE,
    requestedFixture: import.meta.env.VITE_CLASS3_MOCK_FIXTURE,
    localAnalysisUrl: import.meta.env.VITE_CLASS3_ANALYSIS_URL,
  };
  const loadLocal: LocalAnalysisLoader = async (url) => {
    const { loadLocalClass3Analysis } = await import("./localAnalysisAdapter");
    return loadLocalClass3Analysis(url);
  };
  const loadApi: ApiLoader = async () => {
    const { ApiAnalysisAdapter } = await import("./apiAnalysisAdapter");
    const adapter = new ApiAnalysisAdapter();
    return { adapter, status: await adapter.status() };
  };
  if (import.meta.env.DEV && environment.requestedSource === "mock") {
    return resolveClass3PageState(environment, async (fixtureName) => {
      const { loadDevelopmentMock } = await import("../mock/developmentAdapter");
      return loadDevelopmentMock(fixtureName);
    }, loadLocal);
  }
  return resolveClass3PageState(environment, async () => { throw new Error("Development mock loading is disabled."); }, loadLocal, loadApi);
}
