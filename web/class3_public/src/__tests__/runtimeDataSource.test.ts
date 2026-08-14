// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { resolveClass3PageState, selectDataSource } from "../dataSource/runtimeDataSource";
import { syntheticClass3AnalysisPayload } from "../test/class3AnalysisPayload";

const unavailable = "서비스 데이터가 연결되지 않았습니다.";
const mockLoader = vi.fn(async () => { throw new Error("mock should not load"); });

describe("Class 3 runtime data-source boundary", () => {
  it("selects local only when explicitly requested and retains unavailable by default", () => {
    expect(selectDataSource({ mode: "production", requestedSource: "local" })).toBe("local_analysis");
    expect(selectDataSource({ mode: "development", requestedSource: "mock" })).toBe("development_mock");
    expect(selectDataSource({ mode: "production" })).toBe("unavailable");
  });

  it("loads the validated local payload at the configured URL", async () => {
    const loadLocal = vi.fn(async () => syntheticClass3AnalysisPayload);
    const state = await resolveClass3PageState({ mode: "development", requestedSource: "local", localAnalysisUrl: "/analysis.json" }, mockLoader, loadLocal);
    expect(state).toEqual({ kind: "local_analysis", analysis: syntheticClass3AnalysisPayload });
    expect(loadLocal).toHaveBeenCalledWith("/analysis.json");
  });

  it("uses the generated location only in explicitly local mode", async () => {
    const loadLocal = vi.fn(async () => syntheticClass3AnalysisPayload);
    await resolveClass3PageState({ mode: "production", requestedSource: "local" }, mockLoader, loadLocal);
    expect(loadLocal).toHaveBeenCalledWith("/generated/class3-analysis.json");
  });

  it("does not fall back to a mock when local loading fails", async () => {
    const state = await resolveClass3PageState({ mode: "development", requestedSource: "local" }, mockLoader, async () => { throw new Error("bad payload"); });
    expect(state.kind).toBe("error");
    expect(mockLoader).not.toHaveBeenCalled();
  });

  it("does not load either adapter when the source is unavailable", async () => {
    const loadLocal = vi.fn(async () => syntheticClass3AnalysisPayload);
    const state = await resolveClass3PageState({ mode: "production" }, mockLoader, loadLocal);
    expect(state).toEqual({ kind: "unavailable", message: unavailable });
    expect(loadLocal).not.toHaveBeenCalled();
  });
});
