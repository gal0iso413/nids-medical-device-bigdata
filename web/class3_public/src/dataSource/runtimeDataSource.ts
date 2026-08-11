import type { Class3MockFixture } from "../contracts/class3Mock";

export interface RuntimeEnvironment {
  mode: string;
  requestedSource?: string;
  requestedFixture?: string;
}

export type Class3PageState =
  | { kind: "loading"; message: string }
  | { kind: "error"; message: string }
  | { kind: "unavailable"; message: string }
  | { kind: "fixture"; fixture: Class3MockFixture };

export type DevelopmentMockLoader = (
  fixtureName: string,
) => Promise<Class3MockFixture>;

export function selectDataSource(environment: RuntimeEnvironment):
  | "development_mock"
  | "unavailable" {
  if (
    environment.mode === "development" &&
    environment.requestedSource === "mock"
  ) {
    return "development_mock";
  }

  return "unavailable";
}

export async function resolveClass3PageState(
  environment: RuntimeEnvironment,
  loadMock: DevelopmentMockLoader,
): Promise<Class3PageState> {
  if (selectDataSource(environment) !== "development_mock") {
    return {
      kind: "unavailable",
      message: "서비스 데이터 연결 전",
    };
  }

  try {
    const fixture = await loadMock(environment.requestedFixture ?? "released");
    return { kind: "fixture", fixture };
  } catch {
    return {
      kind: "error",
      message: "개발용 mock fixture를 불러오지 못했습니다.",
    };
  }
}

export async function resolveCurrentClass3PageState(): Promise<Class3PageState> {
  if (!import.meta.env.DEV) {
    return {
      kind: "unavailable",
      message: "서비스 데이터 연결 전",
    };
  }

  const environment: RuntimeEnvironment = {
    mode: "development",
    requestedSource: import.meta.env.VITE_CLASS3_DATA_SOURCE,
    requestedFixture: import.meta.env.VITE_CLASS3_MOCK_FIXTURE,
  };

  return resolveClass3PageState(environment, async (fixtureName) => {
    const { loadDevelopmentMock } = await import("../mock/developmentAdapter");
    return loadDevelopmentMock(fixtureName);
  });
}
