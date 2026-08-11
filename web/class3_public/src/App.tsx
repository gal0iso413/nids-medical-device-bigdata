import { useEffect, useState } from "react";
import type { ReleaseStatus } from "./contracts/class3Mock";
import {
  resolveCurrentClass3PageState,
  type Class3PageState,
} from "./dataSource/runtimeDataSource";

const statusLabels: Record<ReleaseStatus, string> = {
  released: "공개 가능 상태 예시",
  suppressed_small_cell: "소수 집단 억제 상태 예시",
  suppressed_dominance: "우세도 억제 상태 예시",
  suppressed_differencing: "차분 위험 억제 상태 예시",
  insufficient_coverage: "데이터 범위 부족 상태 예시",
  not_available: "제공 전 상태 예시",
  empty: "결과 없음 상태 예시",
};

interface AppProps {
  initialState?: Class3PageState;
}
function statusMessage(state: Class3PageState): string {
  if (state.kind === "fixture") {
    return statusLabels[state.fixture.release_status];
  }
  return state.message;
}

export default function App({ initialState }: AppProps) {
  const [state, setState] = useState<Class3PageState>(
    initialState ?? { kind: "loading", message: "화면 상태를 준비하는 중입니다." },
  );

  useEffect(() => {
    if (initialState) {
      return;
    }

    let active = true;
    void resolveCurrentClass3PageState().then((nextState) => {
      if (active) {
        setState(nextState);
      }
    });

    return () => {
      active = false;
    };
  }, [initialState]);

  const fixture = state.kind === "fixture" ? state.fixture : undefined;

  return (
    <main className="app-shell">
      <header className="service-header">
        <p className="eyebrow">Class 3 · 정적 웹 셸</p>
        <h1>업체·품목군 비교분석</h1>
        <p>
          보고된 거래 활동을 품목별 결과와 선택 포트폴리오로 나누어 보는
          공개 서비스의 화면 계약입니다.
        </p>
        <p className="data-boundary">
          현재 production API는 연결되지 않았습니다. 표시 범위와 결측·억제
          상태를 확인한 뒤 결과를 해석해야 합니다.
        </p>
      </header>

      <div className={`state-notice state-${state.kind}`} role="status" aria-live="polite">
        <strong>현재 화면 상태</strong>
        <span>{statusMessage(state)}</span>
      </div>

      <section aria-labelledby="search-heading">
        <h2 id="search-heading">품목군·품목명 검색</h2>
        <div className="field-grid">
          <label>
            품목군 검색
            <input type="search" placeholder="품목군 다중 검색 자리" disabled />
          </label>
          <label>
            품목명 검색
            <input type="search" placeholder="품목명 다중 검색 자리" disabled />
          </label>
        </div>
        <p className="placeholder-note">검색 상호작용은 후속 PR에서 연결합니다.</p>
      </section>

      <section aria-labelledby="selection-heading">
        <h2 id="selection-heading">선택 품목</h2>
        {fixture ? (
          <ul>
            {fixture.selection_summary.selections.map((selection) => (
              <li key={selection.id}>
                <span className="type-badge">{selection.type}</span> {selection.label}
              </li>
            ))}
          </ul>
        ) : (
          <p>선택된 품목이 없습니다.</p>
        )}
      </section>

      <section aria-labelledby="period-heading">
        <h2 id="period-heading">기간 선택</h2>
        <div className="field-grid">
          <label>
            시작 월
            <input type="month" value={fixture?.selection_summary.period.start_month ?? ""} readOnly disabled />
          </label>
          <label>
            종료 월
            <input type="month" value={fixture?.selection_summary.period.end_month ?? ""} readOnly disabled />
          </label>
        </div>
      </section>

      <section aria-labelledby="comparison-heading">
        <h2 id="comparison-heading">품목별 비교 결과</h2>
        {fixture?.per_item_results.length ? (
          <div className="card-grid">
            {fixture.per_item_results.map((result) => (
              <article className="result-card" key={result.selection_id}>
                <h3>{result.selection_type}</h3>
                <p>{result.selection_id}</p>
                <p>{statusLabels[result.release_status]}</p>
                <p>{result.notice}</p>
              </article>
            ))}
          </div>
        ) : (
          <p>{fixture?.release_status === "empty" ? "조건에 맞는 결과가 없습니다." : "비교 결과를 제공할 수 없습니다."}</p>
        )}
      </section>

      <section aria-labelledby="trend-heading">
        <h2 id="trend-heading">월별 추세</h2>
        <div className="placeholder-panel" aria-label="월별 추세 시각화 자리">
          차트 라이브러리 없이 상태와 영역만 정의합니다.
        </div>
      </section>

      <section aria-labelledby="portfolio-heading">
        <h2 id="portfolio-heading">선택 포트폴리오 요약</h2>
        <p>{fixture?.portfolio_summary.notice ?? "포트폴리오 데이터가 연결되지 않았습니다."}</p>
        <p className="placeholder-note">
          품목별 수량과 집중도 지표를 서로 합산하지 않습니다.
        </p>
      </section>

      <section aria-labelledby="reach-heading">
        <h2 id="reach-heading">관측된 유통 도달 구조</h2>
        <p>{fixture?.observed_reach.notice ?? "관측된 도달 구조 데이터가 연결되지 않았습니다."}</p>
        <div className="placeholder-panel" aria-label="관측된 유통 도달 구조 자리">
          최종단 추적이 아닌 관측된 다음 단계의 구조를 표시할 영역입니다.
        </div>
      </section>

      <section aria-labelledby="coverage-heading">
        <h2 id="coverage-heading">데이터 coverage·결측·억제 안내</h2>
        {fixture ? (
          <ul>
            {fixture.coverage.field_states.map((field) => (
              <li key={field.field}>
                <strong>{field.field}</strong>: {field.state} — {field.notice}
              </li>
            ))}
          </ul>
        ) : (
          <p>서비스 데이터 연결 전이므로 coverage를 제공할 수 없습니다.</p>
        )}
      </section>

      <footer aria-label="버전 정보">
        <h2>버전 정보</h2>
        <dl>
          <div><dt>Schema</dt><dd>{fixture?.schema_version ?? "not-connected"}</dd></div>
          <div><dt>Data</dt><dd>{fixture?.data_version ?? "not-connected"}</dd></div>
          <div><dt>Policy</dt><dd>{fixture?.policy_version ?? "not-approved"}</dd></div>
        </dl>
        {fixture && <p>{fixture.development_notice}</p>}
      </footer>
    </main>
  );
}
