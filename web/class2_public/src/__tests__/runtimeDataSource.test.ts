// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { resolveClass2PageState, selectDataSource } from "../dataSource/runtimeDataSource";
import { syntheticClass2AnalysisPayload } from "../test/class2AnalysisPayload";

const unavailable = "서비스 데이터가 연결되지 않았습니다.";
const mockLoader = vi.fn(async () => { throw new Error("mock should not load"); });

describe("Class 2 runtime data-source boundary", () => {
  it("selects local only when explicitly requested and retains unavailable by default", () => {
    expect(selectDataSource({ mode: "production", requestedSource: "api" })).toBe("api");
    expect(selectDataSource({ mode: "production", requestedSource: "local" })).toBe("local_analysis");
    expect(selectDataSource({ mode: "development", requestedSource: "mock" })).toBe("development_mock");
    expect(selectDataSource({ mode: "production" })).toBe("unavailable");
  });

  it("does not fall back to mock or local JSON when API status fails", async () => {
    const loadLocal = vi.fn(async () => syntheticClass2AnalysisPayload);
    const loadApi = vi.fn(async () => { throw new Error("offline"); });
    const state = await resolveClass2PageState({ mode: "development", requestedSource: "api" }, mockLoader, loadLocal, loadApi);
    expect(state.kind).toBe("error");
    expect(mockLoader).not.toHaveBeenCalled();
    expect(loadLocal).not.toHaveBeenCalled();
  });

  it("loads the validated local payload at the configured URL", async () => {
    const loadLocal = vi.fn(async () => syntheticClass2AnalysisPayload);
    const state = await resolveClass2PageState({ mode: "development", requestedSource: "local", localAnalysisUrl: "/analysis.json" }, mockLoader, loadLocal);
    expect(state).toEqual({ kind: "local_analysis", analysis: syntheticClass2AnalysisPayload });
    expect(loadLocal).toHaveBeenCalledWith("/analysis.json");
  });

  it("uses the generated location only in explicitly local mode", async () => {
    const loadLocal = vi.fn(async () => syntheticClass2AnalysisPayload);
    await resolveClass2PageState({ mode: "production", requestedSource: "local" }, mockLoader, loadLocal);
    expect(loadLocal).toHaveBeenCalledWith("/generated/class2-analysis.json");
  });

  it("does not fall back to a mock when local loading fails", async () => {
    const state = await resolveClass2PageState({ mode: "development", requestedSource: "local" }, mockLoader, async () => { throw new Error("bad payload"); });
    expect(state.kind).toBe("error");
    expect(mockLoader).not.toHaveBeenCalled();
  });

  it("does not load either adapter when the source is unavailable", async () => {
    const loadLocal = vi.fn(async () => syntheticClass2AnalysisPayload);
    const state = await resolveClass2PageState({ mode: "production" }, mockLoader, loadLocal);
    expect(state).toEqual({ kind: "unavailable", message: unavailable });
    expect(loadLocal).not.toHaveBeenCalled();
  });
});
