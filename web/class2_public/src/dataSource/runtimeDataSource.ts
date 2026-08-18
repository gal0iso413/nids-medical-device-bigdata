import type { Class2AnalysisPayload } from "../contracts/class2Analysis";
import type { Class2MockFixture } from "../contracts/class2Mock";
import type { ApiAnalysisAdapter, ApiStatus } from "./apiAnalysisAdapter";

export interface RuntimeEnvironment { mode: string; requestedSource?: string; requestedFixture?: string; localAnalysisUrl?: string; }
export type Class2PageState =
  | { kind: "loading"; message: string }
  | { kind: "error"; message: string }
  | { kind: "unavailable"; message: string }
  | { kind: "fixture"; fixture: Class2MockFixture }
  | { kind: "local_analysis"; analysis: Class2AnalysisPayload }
  | { kind: "api"; adapter: ApiAnalysisAdapter; status: ApiStatus };
export type DevelopmentMockLoader = (fixtureName: string) => Promise<Class2MockFixture>;
export type LocalAnalysisLoader = (url: string) => Promise<Class2AnalysisPayload>;
export type ApiLoader = () => Promise<{ adapter: ApiAnalysisAdapter; status: ApiStatus }>;

export function selectDataSource(environment: RuntimeEnvironment): "development_mock" | "local_analysis" | "api" | "unavailable" {
  if (environment.requestedSource === "api") return "api";
  if (environment.requestedSource === "local") return "local_analysis";
  if (environment.mode === "development" && environment.requestedSource === "mock") return "development_mock";
  return "unavailable";
}

export async function resolveClass2PageState(environment: RuntimeEnvironment, loadMock: DevelopmentMockLoader, loadLocal: LocalAnalysisLoader, loadApi?: ApiLoader): Promise<Class2PageState> {
  const source = selectDataSource(environment);
  if (source === "unavailable") return { kind: "unavailable", message: "서비스 데이터가 연결되지 않았습니다." };
  if (source === "local_analysis") {
    try { return { kind: "local_analysis", analysis: await loadLocal(environment.localAnalysisUrl ?? "/generated/class2-analysis.json") }; }
    catch (error) { return { kind: "error", message: `로컬 분석 데이터를 불러오지 못했습니다: ${error instanceof Error ? error.message : "unknown error"}` }; }
  }
  if (source === "api") {
    try { if (!loadApi) throw new Error("API loader is unavailable."); return { kind: "api", ...(await loadApi()) }; }
    catch (error) {
      const detail = error instanceof Error ? error.message : "unknown error";
      return { kind: "error", message: `Local API status check failed. No mock or local-JSON fallback was used. (${detail})` };
    }
  }
  try { return { kind: "fixture", fixture: await loadMock(environment.requestedFixture ?? "released") }; }
  catch { return { kind: "error", message: "개발 mock fixture를 불러오지 못했습니다." }; }
}

export async function resolveCurrentClass2PageState(): Promise<Class2PageState> {
  const environment: RuntimeEnvironment = {
    mode: import.meta.env.DEV ? "development" : "production",
    requestedSource: import.meta.env.VITE_CLASS2_DATA_SOURCE,
    requestedFixture: import.meta.env.VITE_CLASS2_MOCK_FIXTURE,
    localAnalysisUrl: import.meta.env.VITE_CLASS2_ANALYSIS_URL,
  };
  const loadLocal: LocalAnalysisLoader = async (url) => {
    const { loadLocalClass2Analysis } = await import("./localAnalysisAdapter");
    return loadLocalClass2Analysis(url);
  };
  const loadApi: ApiLoader = async () => {
    const { ApiAnalysisAdapter } = await import("./apiAnalysisAdapter");
    const adapter = new ApiAnalysisAdapter();
    return { adapter, status: await adapter.status() };
  };
  if (import.meta.env.DEV && environment.requestedSource === "mock") {
    return resolveClass2PageState(environment, async (fixtureName) => {
      const { loadDevelopmentMock } = await import("../mock/developmentAdapter");
      return loadDevelopmentMock(fixtureName);
    }, loadLocal);
  }
  return resolveClass2PageState(environment, async () => { throw new Error("Development mock loading is disabled."); }, loadLocal, loadApi);
}
