// @vitest-environment node

import { describe, expect, it, vi } from "vitest";
import { loadDevelopmentMock } from "../mock/developmentAdapter";
import {
  resolveClass3PageState,
  selectDataSource,
} from "../dataSource/runtimeDataSource";

describe("Class 3 runtime data-source boundary", () => {
  it("selects mock only in development with an explicit setting", () => {
    expect(selectDataSource({ mode: "development", requestedSource: "mock" })).toBe(
      "development_mock",
    );
    expect(selectDataSource({ mode: "development" })).toBe("unavailable");
    expect(selectDataSource({ mode: "test", requestedSource: "mock" })).toBe(
      "unavailable",
    );
  });

  it("never selects or loads the mock adapter in production", async () => {
    const loadMock = vi.fn(async () => loadDevelopmentMock("released"));
    const state = await resolveClass3PageState(
      {
        mode: "production",
        requestedSource: "mock",
        requestedFixture: "released",
      },
      loadMock,
    );

    expect(state).toEqual({ kind: "unavailable", message: "서비스 데이터 연결 전" });
    expect(loadMock).not.toHaveBeenCalled();
  });

  it("loads the explicitly selected development fixture", async () => {
    const loadMock = vi.fn(async () => loadDevelopmentMock("empty"));
    const state = await resolveClass3PageState(
      {
        mode: "development",
        requestedSource: "mock",
        requestedFixture: "empty",
      },
      loadMock,
    );

    expect(state.kind).toBe("fixture");
    expect(loadMock).toHaveBeenCalledWith("empty");
  });

  it("returns an explicit development error instead of another fixture", async () => {
    const state = await resolveClass3PageState(
      { mode: "development", requestedSource: "mock", requestedFixture: "unknown" },
      async () => {
        throw new Error("unknown fixture");
      },
    );

    expect(state).toEqual({
      kind: "error",
      message: "개발용 mock fixture를 불러오지 못했습니다.",
    });
  });
});
