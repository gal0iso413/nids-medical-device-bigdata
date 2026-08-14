import { useEffect, useMemo, useState } from "react";
import type {
  ReleaseStatus,
  SelectionItem,
  SelectionType,
} from "./contracts/class3Mock";
import type {
  Class3AnalysisPayload,
  Class3SelectionCatalogRow,
} from "./contracts/class3Analysis";
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

interface PeriodState {
  startMonth: string;
  endMonth: string;
}

interface LocalSelectionItem extends SelectionItem {
  parentLabel?: string | null;
}

function localPeriod(analysis: Class3AnalysisPayload): PeriodState {
  const summaries = analysis.selection_coverage_summary;
  return {
    startMonth: summaries.map((summary) => summary.period_start).sort()[0] ?? "",
    endMonth: summaries.map((summary) => summary.period_end).sort().at(-1) ?? "",
  };
}

function isMonthInPeriod(month: string, period: PeriodState): boolean {
  const start = period.startMonth.replace("-", "");
  const end = period.endMonth.replace("-", "");
  return (!start || month >= start) && (!end || month <= end);
}

function decimalDisplay(value: string | null): string {
  return value ?? "검증된 값 없음";
}

function statusMessage(state: Class3PageState): string {
  if (state.kind === "local_analysis") {
    return "로컬 분석 데이터 · 공개 정책 미적용";
  }
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
  if (state.kind === "local_analysis") {
    return "attention";
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
  const initialFixture = initialState?.kind === "fixture" ? initialState.fixture : undefined;
  const initialLocalAnalysis = initialState?.kind === "local_analysis"
    ? initialState.analysis
    : undefined;
  const [searchQuery, setSearchQuery] = useState("");
  const [searchIsOpen, setSearchIsOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>(
    initialFixture?.selection_summary.selections.map((selection) => selection.id) ?? [],
  );
  const [periodDraft, setPeriodDraft] = useState<PeriodState>({
    startMonth: initialFixture?.selection_summary.period.start_month
      ?? (initialLocalAnalysis ? localPeriod(initialLocalAnalysis).startMonth : ""),
    endMonth: initialFixture?.selection_summary.period.end_month
      ?? (initialLocalAnalysis ? localPeriod(initialLocalAnalysis).endMonth : ""),
  });
  const [appliedPeriod, setAppliedPeriod] = useState<PeriodState>({
    startMonth: initialFixture?.selection_summary.period.start_month
      ?? (initialLocalAnalysis ? localPeriod(initialLocalAnalysis).startMonth : ""),
    endMonth: initialFixture?.selection_summary.period.end_month
      ?? (initialLocalAnalysis ? localPeriod(initialLocalAnalysis).endMonth : ""),
  });

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
  const localAnalysis = state.kind === "local_analysis" ? state.analysis : undefined;
  const stateKey = fixture
    ? `${fixture.data_version}:${fixture.release_status}:${fixture.view_state}`
    : localAnalysis
    ? `local:${localAnalysis.analysis_schema_version}:${localAnalysis.selection_catalog.length}`
    : "no-fixture";

  useEffect(() => {
    if (localAnalysis) {
      const nextPeriod = localPeriod(localAnalysis);
      setSelectedIds([]);
      setPeriodDraft(nextPeriod);
      setAppliedPeriod(nextPeriod);
      setSearchQuery("");
      setSearchIsOpen(false);
      return;
    }
    if (!fixture) {
      setSelectedIds([]);
      setPeriodDraft({ startMonth: "", endMonth: "" });
      setAppliedPeriod({ startMonth: "", endMonth: "" });
      return;
    }

    const nextPeriod = {
      startMonth: fixture.selection_summary.period.start_month,
      endMonth: fixture.selection_summary.period.end_month,
    };
    setSelectedIds(fixture.selection_summary.selections.map((selection) => selection.id));
    setPeriodDraft(nextPeriod);
    setAppliedPeriod(nextPeriod);
    setSearchQuery("");
    setSearchIsOpen(false);
  }, [stateKey]);

  const candidateSelections: LocalSelectionItem[] = localAnalysis
    ? localAnalysis.selection_catalog.map((selection: Class3SelectionCatalogRow) => ({
      id: selection.selection_id,
      type: selection.selection_type,
      label: selection.label,
      parentLabel: selection.parent_item_group_label,
    }))
    : fixture?.selection_summary.selections ?? [];
  const selectedIdSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const selectedSelections = candidateSelections.filter((selection) =>
    selectedIdSet.has(selection.id),
  );
  const normalizedQuery = searchQuery.trim().toLocaleLowerCase();
  const filteredCandidates = candidateSelections.filter((selection) => {
    if (!normalizedQuery) {
      return true;
    }
    return [
      selection.label,
      selection.type,
      selectionTypeLabels[selection.type],
      selection.parentLabel ?? "",
    ]
      .some((value) => value.toLocaleLowerCase().includes(normalizedQuery));
  });
  const selectedResults = (fixture?.per_item_results ?? []).filter((result) =>
    selectedIdSet.has(result.selection_id),
  );
  const selectedComposition = fixture?.portfolio_summary.released_composition?.entries
    .filter((entry) => selectedIdSet.has(entry.selection_id)) ?? [];
  const periodIsInvalid = Boolean(
    periodDraft.startMonth
      && periodDraft.endMonth
      && periodDraft.startMonth > periodDraft.endMonth,
  );
  const localMetrics = localAnalysis?.selection_month_metrics.filter((metric) =>
    selectedIdSet.has(metric.selection_id) && isMonthInPeriod(metric.month, appliedPeriod),
  ) ?? [];
  const localComposition = localAnalysis?.selection_month_composition.filter((entry) =>
    selectedIdSet.has(entry.selection_id) && isMonthInPeriod(entry.month, appliedPeriod),
  ) ?? [];
  const localCoverage = localAnalysis?.selection_coverage_summary.filter((summary) =>
    selectedIdSet.has(summary.selection_id),
  ) ?? [];
  const periodCanApply = Boolean(
    (fixture || localAnalysis)
      && periodDraft.startMonth
      && periodDraft.endMonth
      && !periodIsInvalid,
  );

  function addSelection(selection: LocalSelectionItem) {
    setSelectedIds((currentIds) =>
      currentIds.includes(selection.id) ? currentIds : [...currentIds, selection.id],
    );
  }

  function removeSelection(selection: LocalSelectionItem) {
    setSelectedIds((currentIds) => currentIds.filter((id) => id !== selection.id));
  }

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
            {localAnalysis
              ? "로컬 분석 데이터 · 공개 정책 미적용"
              : fixture ? "합성 개발 데이터" : "서비스 데이터 미연결"}
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
            {localAnalysis
              ? "로컬 분석은 공개 정책이 적용되지 않은 상태입니다. 공급 활동을 판매량·수요·시장 성장으로 해석하지 않습니다."
              : "현재 production API는 연결되지 않았습니다. 표시 범위와 결측·억제 상태를 확인한 뒤 결과를 해석해야 합니다."}
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
              value={searchQuery}
              onChange={(event) => {
                setSearchQuery(event.target.value);
                setSearchIsOpen(true);
              }}
              onFocus={() => setSearchIsOpen(true)}
              aria-describedby="search-help search-status"
              aria-controls="selection-search-results"
              aria-expanded={searchIsOpen}
              autoComplete="off"
              disabled={!fixture && !localAnalysis}
            />
          </label>
          <p id="search-help" className="placeholder-note">
            {localAnalysis
              ? "전체 local selection catalog를 검색합니다."
              : "현재 synthetic fixture에 포함된 품목만 검색합니다."}
          </p>
          <p id="search-status" className="sr-only" aria-live="polite">
            {searchIsOpen
              ? `검색 결과 ${filteredCandidates.length}개`
              : "검색 결과 닫힘"}
          </p>
          {(fixture || localAnalysis) && searchIsOpen && (
            <ul
              id="selection-search-results"
              className="search-results"
              aria-label="품목 검색 결과"
            >
              {filteredCandidates.length ? (
                filteredCandidates.map((selection) => {
                  const isSelected = selectedIdSet.has(selection.id);
                  return (
                    <li key={selection.id}>
                      <button
                        type="button"
                        className="search-result-button"
                        onClick={() => addSelection(selection)}
                        disabled={isSelected}
                      >
                        <span className="type-badge">
                          {selectionTypeLabels[selection.type]}
                        </span>
                        <span className="synthetic-label">{selection.label}</span>
                        {selection.type === "item_name" && selection.parentLabel && (
                          <span>상위 품목군: {selection.parentLabel}</span>
                        )}
                        <span className="search-result-state">
                          {isSelected ? "선택됨" : "선택"}
                        </span>
                      </button>
                    </li>
                  );
                })
              ) : (
                <li className="search-empty" role="status">
                  fixture 안에서 일치하는 품목을 찾지 못했습니다.
                </li>
              )}
            </ul>
          )}
        </section>

        <div className="filter-strip">
          <section className="selection-panel" aria-labelledby="selection-heading">
            <h2 id="selection-heading">선택 품목</h2>
            {selectedSelections.length ? (
              <ul className="selection-list">
                {selectedSelections.map((selection) => (
                  <li key={selection.id}>
                    <span className="type-badge">
                      {selectionTypeLabels[selection.type]}
                    </span>
                    <span className="synthetic-label">{selection.label}</span>
                    {selection.type === "item_name" && selection.parentLabel && (
                      <span>상위 품목군: {selection.parentLabel}</span>
                    )}
                    <button
                      type="button"
                      className="remove-selection"
                      onClick={() => removeSelection(selection)}
                      aria-label={`${selection.label} 선택 제거`}
                    >
                      제거
                    </button>
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
                  value={periodDraft.startMonth}
                  onChange={(event) => setPeriodDraft((current) => ({
                    ...current,
                    startMonth: event.target.value,
                  }))}
                  aria-invalid={periodIsInvalid}
                  aria-describedby={periodIsInvalid ? "period-error" : undefined}
                  disabled={!fixture && !localAnalysis}
                />
              </label>
              <label>
                종료 월
                <input
                  type="month"
                  value={periodDraft.endMonth}
                  onChange={(event) => setPeriodDraft((current) => ({
                    ...current,
                    endMonth: event.target.value,
                  }))}
                  aria-invalid={periodIsInvalid}
                  aria-describedby={periodIsInvalid ? "period-error" : undefined}
                  disabled={!fixture && !localAnalysis}
                />
              </label>
            </div>
            {periodIsInvalid && (
              <p id="period-error" className="field-error" role="alert">
                시작 월은 종료 월보다 늦을 수 없습니다.
              </p>
            )}
            <button
              type="button"
              className="period-apply"
              disabled={!periodCanApply}
              onClick={() => setAppliedPeriod(periodDraft)}
            >
              기간 적용
            </button>
            <p className="period-note" aria-live="polite">
              화면 비교 범위: {appliedPeriod.startMonth || "미설정"} ~ {appliedPeriod.endMonth || "미설정"}
              <span>기간을 바꿔도 mock 분석값은 재계산하지 않습니다.</span>
            </p>
          </section>
        </div>

        <section className="results-section" aria-labelledby="comparison-heading">
          <div className="section-heading section-heading--rule">
            <p className="section-kicker">품목별 보기</p>
            <h2 id="comparison-heading">품목별 비교 결과</h2>
          </div>
          {localAnalysis && localMetrics.length ? (
            <div className="card-grid">
              {localMetrics.map((metric) => (
                <article className="result-card" key={`${metric.selection_id}:${metric.month}`}>
                  <div className="result-card__header">
                    <h3>{metric.month} · {selectionTypeLabels[metric.selection_type]}</h3>
                    <span className="synthetic-label">{metric.selection_id}</span>
                  </div>
                  <dl className="released-content">
                    <div><dt>월별 거래 건수</dt><dd>{metric.tx_count ?? "없음"}</dd></div>
                    <div><dt>공급금액</dt><dd>{decimalDisplay(metric.amount_sum_clean)}</dd></div>
                    <div><dt>원시 공급수량</dt><dd>{decimalDisplay(metric.raw_supply_qty_sum)}</dd></div>
                    {metric.piece_qty_sum !== null && <div><dt>낱개수량 (검증됨)</dt><dd>{metric.piece_qty_sum}</dd></div>}
                    <div><dt>금액 coverage</dt><dd>{decimalDisplay(metric.amount_coverage)}</dd></div>
                    <div><dt>원시 수량 coverage</dt><dd>{decimalDisplay(metric.raw_supply_qty_coverage)}</dd></div>
                    <div><dt>월별 공급자 수</dt><dd>{metric.unique_supplier_count ?? "없음"}</dd></div>
                    <div><dt>월별 수령자 수</dt><dd>{metric.unique_receiver_count ?? "없음"}</dd></div>
                    <div><dt>quality flags</dt><dd>{metric.quality_flags || "없음"}</dd></div>
                  </dl>
                </article>
              ))}
            </div>
          ) : selectedResults.length ? (
            <div className="card-grid">
              {selectedResults.map((result) => (
                <article className="result-card" key={result.selection_id}>
                  <div className="result-card__header">
                    <h3>{selectionTypeLabels[result.selection_type]}</h3>
                    <span className="status-chip">
                      {statusLabels[result.release_status]}
                    </span>
                  </div>
                  <p className="synthetic-label">{result.selection_id}</p>
                  <p>{result.notice}</p>
                  {result.released_content && (
                    <dl className="released-content">
                      <div><dt>보고된 거래 활동</dt><dd>{result.released_content.activity_label}</dd></div>
                      <div><dt>공급 수량</dt><dd>{result.released_content.quantity_label}</dd></div>
                      <div><dt>월별 추세</dt><dd>{result.released_content.trend_label}</dd></div>
                    </dl>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <p className="empty-copy empty-copy--prominent">
              {!selectedSelections.length
                ? "선택된 품목이 없습니다. 검색 결과에서 품목을 선택해 주세요."
                : fixture?.view_state === "empty"
                ? "조건에 맞는 결과가 없습니다."
                : localAnalysis
                ? "적용 기간에 표시할 선택 품목 결과가 없습니다."
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
            <strong>향후 monthly series 연결 영역</strong>
            {localAnalysis && localComposition.length ? (
              <ul className="trend-list">
                {localComposition.map((entry) => (
                  <li key={`${entry.selection_id}:${entry.month}:${entry.dimension}:${entry.dimension_value}`}>
                    <span>{entry.month} · {entry.dimension}</span>
                    <span>{entry.dimension_value}{entry.is_unknown ? " (unknown)" : ""}</span>
                    <span>{entry.endpoint_count ?? "없음"} / {entry.denominator_endpoint_count ?? "없음"} · {decimalDisplay(entry.endpoint_share)} · flags: {entry.quality_flags || "없음"}</span>
                  </li>
                ))}
              </ul>
            ) : selectedResults.length ? (
              <ul className="trend-list">
                {selectedResults.map((result) => (
                  <li key={result.selection_id}>
                    <span className="type-badge">{selectionTypeLabels[result.selection_type]}</span>
                    <span className="synthetic-label">{result.selection_id}</span>
                    {result.released_content ? (
                      <span>{result.released_content.trend_label}</span>
                    ) : (
                      <span>{statusLabels[result.release_status]} — {result.notice}</span>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <span>선택된 품목의 추세 표시가 없습니다.</span>
            )}
            <span className="placeholder-note">
              {localAnalysis
                ? "이는 관측된 공급자·수령자 endpoint 구성이며 최종 의료기관 추적을 의미하지 않습니다."
                : "실제 월별 series나 가짜 선 그래프는 포함하지 않습니다."}
            </span>
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
            {selectedComposition.length > 0 && (
              <ul className="composition-list">
                {selectedComposition.map((entry) => (
                  <li key={entry.selection_id}>
                    <span className="synthetic-label">{entry.selection_id}</span>
                    <span>{entry.share_label}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="placeholder-note">
              {fixture?.portfolio_summary.released_composition?.non_additive_notice
                ?? "품목별 수량과 집중도 지표를 서로 합산하지 않습니다."}
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
              <p>최종단 추적이 아닌 관측된 다음 단계의 구조를 표시할 영역입니다.</p>
              {fixture?.observed_reach.released_stages && (
                <ul className="reach-list">
                  {fixture.observed_reach.released_stages.map((stage) => (
                    <li key={stage.stage_label}>
                      <span>{stage.stage_label}</span>
                      <span>{stage.display_label}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>

        <section className="coverage-section" aria-labelledby="coverage-heading">
          <div className="section-heading">
            <p className="section-kicker">공개 범위 확인</p>
            <h2 id="coverage-heading">데이터 coverage·결측·억제 안내</h2>
          </div>
          {localAnalysis ? (
            localCoverage.length ? (
              <ul className="coverage-grid">
                {localCoverage.map((summary) => {
                  const differsFromApplied = summary.period_start !== appliedPeriod.startMonth.replace("-", "")
                    || summary.period_end !== appliedPeriod.endMonth.replace("-", "");
                  return (
                    <li key={summary.selection_id}>
                      <strong>{summary.selection_id}</strong>
                      <span>summary 생성 기간: {summary.period_start} ~ {summary.period_end}</span>
                      {differsFromApplied && <span>현재 적용 기간과 다르며, 아래 coverage는 summary 생성 기간 기준입니다.</span>}
                      <span>포함 월: {summary.included_months.join(", ") || "없음"}</span>
                      <span>누락 월: {summary.missing_months.join(", ") || "없음"}</span>
                      <span>금액 valid rate: {decimalDisplay(summary.amount_valid_rate)}</span>
                      <span>원시 수량 valid rate: {decimalDisplay(summary.raw_supply_qty_valid_rate)}</span>
                      <span>낱개수량 valid rate: {decimalDisplay(summary.piece_qty_valid_rate)}</span>
                      <span>quality flags: {summary.quality_flags || "없음"}</span>
                    </li>
                  );
                })}
              </ul>
            ) : <p className="empty-copy">선택한 품목의 coverage 요약이 없습니다.</p>
          ) : fixture ? (
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
            <div><dt>Schema</dt><dd>{localAnalysis?.analysis_schema_version ?? fixture?.schema_version ?? "not-connected"}</dd></div>
            <div><dt>Data</dt><dd>{localAnalysis ? "selection coverage summary 참조" : fixture?.data_version ?? "not-connected"}</dd></div>
            <div><dt>Policy</dt><dd>{localAnalysis ? "공개 정책 미적용" : fixture?.policy_version ?? "not-approved"}</dd></div>
          </dl>
          {fixture && <p>{fixture.development_notice}</p>}
          {localAnalysis && <p>로컬 분석은 공개 서비스 승인 또는 공개 보호 처리 상태가 아닙니다.</p>}
        </footer>
      </main>
    </>
  );
}
