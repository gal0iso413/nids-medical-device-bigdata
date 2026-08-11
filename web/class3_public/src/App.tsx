import { useEffect, useState } from "react";
import type { ReleaseStatus, SelectionType } from "./contracts/class3Mock";
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
};

const selectionTypeLabels: Record<SelectionType, string> = {
  item_group: "품목군",
  item_name: "품목명",
};

interface AppProps {
  initialState?: Class3PageState;
}

function statusMessage(state: Class3PageState): string {
  if (state.kind === "fixture") {
    if (state.fixture.view_state === "empty") {
      return "결과 없음 상태 예시";
    }
    return statusLabels[state.fixture.release_status];
  }
  return state.message;
}

function statusTone(state: Class3PageState): string {
  if (state.kind === "error") {
    return "danger";
  }
  if (state.kind !== "fixture") {
    return "neutral";
  }
  if (state.fixture.view_state === "empty") {
    return "empty";
  }
  if (state.fixture.release_status === "released") {
    return "released";
  }
  if (state.fixture.release_status === "not_available") {
    return "neutral";
  }
  return "attention";
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
    <>
      <a className="skip-link" href="#main-content">
        본문 바로가기
      </a>

      <header className="service-bar">
        <div className="service-bar__inner">
          <div className="service-brand" aria-label="NIDS Class 3 공개 비교 서비스">
            <span className="nids-mark" aria-hidden="true">NIDS</span>
            <span className="service-brand__text">
              <span className="service-kicker">의료기기 통합정보</span>
              <span className="service-name">Class 3 공개 비교</span>
            </span>
          </div>
          <span className={`environment-badge${fixture ? " is-synthetic" : ""}`}>
            {fixture ? "합성 개발 데이터" : "서비스 데이터 미연결"}
          </span>
        </div>
      </header>

      <main id="main-content" className="app-shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">공개 비교 분석</p>
          <h1>업체·품목군 비교분석</h1>
          <p className="hero-lead">
            보고된 거래 활동을 품목별 결과와 선택 포트폴리오로 나누어 보는
            공개 서비스의 화면 계약입니다.
          </p>
          <p className="data-boundary" role="note">
            현재 production API는 연결되지 않았습니다. 표시 범위와 결측·억제
            상태를 확인한 뒤 결과를 해석해야 합니다.
          </p>
        </header>

        <div
          className={`state-notice state-${statusTone(state)}`}
          role="status"
          aria-live="polite"
        >
          <strong>현재 화면 상태</strong>
          <span>{statusMessage(state)}</span>
        </div>

        <section className="search-panel" aria-labelledby="search-heading">
          <div className="section-heading">
            <p className="section-kicker">비교 조건</p>
            <h2 id="search-heading">품목군·품목명 검색</h2>
          </div>
          <label className="search-label">
            품목군 또는 품목명 검색
            <input
              type="search"
              placeholder="품목군·품목명을 한 번에 검색하는 영역"
              aria-describedby="search-help"
              disabled
            />
          </label>
          <p id="search-help" className="placeholder-note">
            검색 상호작용은 후속 PR에서 연결합니다.
          </p>
        </section>

        <div className="filter-strip">
          <section className="selection-panel" aria-labelledby="selection-heading">
            <h2 id="selection-heading">선택 품목</h2>
            {fixture ? (
              <ul className="selection-list">
                {fixture.selection_summary.selections.map((selection) => (
                  <li key={selection.id}>
                    <span className="type-badge">
                      {selectionTypeLabels[selection.type]}
                    </span>
                    <span className="synthetic-label">{selection.label}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-copy">선택된 품목이 없습니다.</p>
            )}
          </section>

          <section className="period-panel" aria-labelledby="period-heading">
            <h2 id="period-heading">기간 선택</h2>
            <div className="field-grid">
              <label>
                시작 월
                <input
                  type="month"
                  value={fixture?.selection_summary.period.start_month ?? ""}
                  readOnly
                  disabled
                />
              </label>
              <label>
                종료 월
                <input
                  type="month"
                  value={fixture?.selection_summary.period.end_month ?? ""}
                  readOnly
                  disabled
                />
              </label>
            </div>
          </section>
        </div>

        <section className="results-section" aria-labelledby="comparison-heading">
          <div className="section-heading section-heading--rule">
            <p className="section-kicker">품목별 보기</p>
            <h2 id="comparison-heading">품목별 비교 결과</h2>
          </div>
          {fixture?.per_item_results.length ? (
            <div className="card-grid">
              {fixture.per_item_results.map((result) => (
                <article className="result-card" key={result.selection_id}>
                  <div className="result-card__header">
                    <h3>{selectionTypeLabels[result.selection_type]}</h3>
                    <span className="status-chip">
                      {statusLabels[result.release_status]}
                    </span>
                  </div>
                  <p className="synthetic-label">{result.selection_id}</p>
                  <p>{result.notice}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="empty-copy empty-copy--prominent">
              {fixture?.view_state === "empty"
                ? "조건에 맞는 결과가 없습니다."
                : "비교 결과를 제공할 수 없습니다."}
            </p>
          )}
        </section>

        <section className="trend-section" aria-labelledby="trend-heading">
          <div className="section-heading">
            <p className="section-kicker">기간별 보기</p>
            <h2 id="trend-heading">월별 추세</h2>
          </div>
          <div className="placeholder-panel" aria-label="월별 추세 시각화 자리">
            <strong>월별 추세 영역</strong>
            <span>차트 라이브러리 없이 상태와 영역만 정의합니다.</span>
          </div>
        </section>

        <div className="insight-grid">
          <section className="portfolio-panel" aria-labelledby="portfolio-heading">
            <p className="section-kicker">구성 요약</p>
            <h2 id="portfolio-heading">선택 포트폴리오 요약</h2>
            <p>
              {fixture?.portfolio_summary.notice ??
                "포트폴리오 데이터가 연결되지 않았습니다."}
            </p>
            <p className="placeholder-note">
              품목별 수량과 집중도 지표를 서로 합산하지 않습니다.
            </p>
          </section>

          <section className="reach-panel" aria-labelledby="reach-heading">
            <p className="section-kicker">관측 범위</p>
            <h2 id="reach-heading">관측된 유통 도달 구조</h2>
            <p>
              {fixture?.observed_reach.notice ??
                "관측된 도달 구조 데이터가 연결되지 않았습니다."}
            </p>
            <div className="reach-placeholder" aria-label="관측된 유통 도달 구조 자리">
              최종단 추적이 아닌 관측된 다음 단계의 구조를 표시할 영역입니다.
            </div>
          </section>
        </div>

        <section className="coverage-section" aria-labelledby="coverage-heading">
          <div className="section-heading">
            <p className="section-kicker">공개 범위 확인</p>
            <h2 id="coverage-heading">데이터 coverage·결측·억제 안내</h2>
          </div>
          {fixture ? (
            <ul className="coverage-grid">
              {fixture.coverage.field_states.map((field) => (
                <li key={field.field}>
                  <strong>{field.field}</strong>
                  <span className="coverage-state">상태: {field.state}</span>
                  <span>{field.notice}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-copy">
              서비스 데이터 연결 전이므로 coverage를 제공할 수 없습니다.
            </p>
          )}
        </section>

        <footer className="methodology-footer" aria-label="버전 정보">
          <h2>버전 정보</h2>
          <dl>
            <div><dt>Schema</dt><dd>{fixture?.schema_version ?? "not-connected"}</dd></div>
            <div><dt>Data</dt><dd>{fixture?.data_version ?? "not-connected"}</dd></div>
            <div><dt>Policy</dt><dd>{fixture?.policy_version ?? "not-approved"}</dd></div>
          </dl>
          {fixture && <p>{fixture.development_notice}</p>}
        </footer>
      </main>
    </>
  );
}
