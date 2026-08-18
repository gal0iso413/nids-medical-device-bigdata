import { useEffect, useState, type FormEvent } from "react";
import { Ready } from "./App";
import type { LoadState } from "./dataSource";
import {
  LookupEntityMissingError,
  LookupMonthUnavailableError,
  type ApiStatus,
  type CatalogHit,
  type Class1LookupAdapter,
  type ReviewQueue,
  type ReviewQueueItem,
} from "./apiLookupAdapter";
import { roleLabel } from "./labels";

interface Props {
  adapter: Class1LookupAdapter;
  status: ApiStatus;
}

const MISSING_NAME = "표시명 없음";
const ENTITY_ABSENT = "이 업체는 해당 앵커 창에 없습니다";
const MONTH_ABSENT = "선택한 앵커월의 조회 인덱스가 없습니다";

function hitLabel(hit: { display_name: string | null }) {
  const name = hit.display_name?.trim();
  return name ? name : MISSING_NAME;
}

function formatPercentile(value: number) {
  return String(Number(value.toFixed(1)));
}

function queueMeta(item: ReviewQueueItem) {
  const bits = [
    `유통업체군 백분위 ${formatPercentile(item.review_priority_percentile)}`,
    item.region ? item.region : null,
    item.name_conflict ? "표기 충돌" : null,
  ].filter(Boolean);
  return bits.join(" · ");
}

function availableMonths(status: ApiStatus) {
  if (Array.isArray(status.available_anchor_months) && status.available_anchor_months.length > 0) {
    return status.available_anchor_months;
  }
  return [status.anchor_month];
}

function defaultMonth(status: ApiStatus) {
  return status.default_anchor_month ?? status.anchor_month;
}

function lookupErrorMessage(error: unknown) {
  if (error instanceof LookupEntityMissingError) return ENTITY_ABSENT;
  if (error instanceof LookupMonthUnavailableError) return MONTH_ABSENT;
  return "해당 업체를 조회하지 못했습니다.";
}

export default function ApiModeApp({ adapter, status }: Props) {
  const months = availableMonths(status);
  const [anchorMonth, setAnchorMonth] = useState(defaultMonth(status));
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<CatalogHit[]>([]);
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [state, setState] = useState<LoadState | { kind: "idle" }>({ kind: "idle" });

  useEffect(() => {
    setHits([]);
    setQueue(null);
    setQueueError(null);
    void adapter.reviewQueue(anchorMonth)
      .then((payload) => {
        setQueue(payload);
        setQueueError(null);
      })
      .catch((error) => {
        setQueue(null);
        setQueueError(error instanceof LookupMonthUnavailableError ? MONTH_ABSENT : "유통업체 검토 목록을 읽지 못했습니다.");
      });
  }, [adapter, anchorMonth]);

  useEffect(() => {
    const selected = query.trim();
    if (!selected) {
      setHits([]);
      return;
    }
    const handle = window.setTimeout(() => {
      void adapter.search(selected, 20, anchorMonth).then(setHits).catch(() => setHits([]));
    }, 200);
    return () => window.clearTimeout(handle);
  }, [adapter, query, anchorMonth]);

  async function lookupHit(hit: { entity_id: string; display_name: string | null }) {
    setQuery(hitLabel(hit));
    setHits([]);
    setSelectedId(hit.entity_id);
    setState({ kind: "loading" });
    try {
      setState(await adapter.lookup(hit.entity_id, anchorMonth));
    } catch (error) {
      setState({ kind: "error", message: lookupErrorMessage(error) });
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const selected = query.trim();
    if (!selected) {
      setState({ kind: "error", message: "조회할 업체명을 입력하십시오." });
      return;
    }
    const matches = hits.length > 0 ? hits : await adapter.search(selected, 20, anchorMonth).catch(() => []);
    if (matches.length === 1) {
      await lookupHit(matches[0]);
      return;
    }
    if (matches.length === 0) {
      setState({ kind: "error", message: "일치하는 업체명이 없습니다. 목록에서 선택하거나 다른 이름을 입력하십시오." });
      return;
    }
    setHits(matches);
    setState({ kind: "error", message: "같은 이름이 여러 업체에 있습니다. 목록에서 선택하십시오." });
  }

  async function onAnchorChange(next: string) {
    setAnchorMonth(next);
    setHits([]);
    if (!selectedId) {
      setState({ kind: "idle" });
      return;
    }
    setState({ kind: "loading" });
    try {
      setState(await adapter.lookup(selectedId, next));
    } catch (error) {
      setState({ kind: "error", message: lookupErrorMessage(error) });
    }
  }

  return (
    <>
      <a className="skip" href="#main-content">본문으로 건너뛰기</a>
      <div className="shell">
      <header className="hero">
        <p className="eyebrow">NIDS · CLASS 1</p>
        <h1>내부 거래 관계 모니터링</h1>
        <p>로컬 조회 API · 내부 전용 · 요청 시 학습 없음 · 공개 정책 미적용</p>
      </header>
      <section className="status">
        <strong>조회 인덱스</strong>
        <span>앵커월 {anchorMonth} · 분석 구간 {(queue?.window_months ?? status.window_months).join(" ~ ")}</span>
        <span>인덱스 업체 {status.entity_count} · 간선 {status.edge_count}</span>
        <span>상태: 로컬 조회 전용</span>
      </section>
      <form className="anchor-form" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="anchor-month">완료 앵커월</label>
        <select
          id="anchor-month"
          name="anchor-month"
          value={anchorMonth}
          onChange={(event) => void onAnchorChange(event.target.value)}
        >
          {months.map((month) => (
            <option key={month} value={month}>{month}</option>
          ))}
        </select>
      </form>
      <section className="review-queue" aria-labelledby="review-queue-heading">
        <h2 id="review-queue-heading">유통업체 검토 우선순위 상위 10곳</h2>
        <p>해당 앵커월·해당 역할군 안의 상대 순위입니다. 목록에서 고르면 해당 업체의 1-hop이 열립니다.</p>
        {queueError ? <p>{queueError}</p> : null}
        {queue && queue.entities.length === 0 ? (
          <p>유통업체군에서 검토 우선순위를 매길 수 있는 업체가 없습니다.</p>
        ) : null}
        {queue && queue.entities.length > 0 ? (
          <ol>
            {queue.entities.map((item) => (
              <li key={item.entity_id}>
                <button
                  type="button"
                  className={item.entity_id === selectedId ? "is-active" : undefined}
                  onClick={() => void lookupHit(item)}
                >
                  <span>
                    {item.rank}. {hitLabel(item)}
                    <small>{queueMeta(item)}</small>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        ) : null}
      </section>
      <form className="lookup-form" onSubmit={(event) => void onSubmit(event)}>
        <label htmlFor="company-name">업체명</label>
        <div className="lookup-field">
          <input
            id="company-name"
            name="company-name"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          {hits.length > 0 ? (
            <ul className="lookup-suggest">
              {hits.map((hit) => (
                <li key={hit.entity_id}>
                  <button type="button" onClick={() => void lookupHit(hit)}>
                    {hitLabel(hit)}
                    <small>{roleLabel(hit.role_group)}{hit.region ? ` · ${hit.region}` : ""}{hit.name_conflict ? " · 표기 충돌" : ""}</small>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <button type="submit">조회</button>
      </form>
      {state.kind === "idle" ? <p className="lookup-hint">특정 업체를 알고 있으면 한글 업체명으로 조회하십시오. 같은 이름이 여러 면허에 있으면 목록에서 고르십시오.</p> : null}
      </div>
      {state.kind === "loading" ? <main className="shell"><p>조회 인덱스를 읽는 중입니다.</p></main> : null}
      {state.kind === "error" ? <main id="main-content" className="shell empty-state" tabIndex={-1}><h2>조회할 수 없습니다</h2><p>{state.message}</p></main> : null}
      {state.kind === "ready" ? <Ready key={`${anchorMonth}:${state.graph.selected_entity_id}`} state={state} hideHeader footer="다른 업체는 위 검토 목록 또는 업체명 조회로 바꾸십시오. 요청마다 모델을 학습하지 않습니다." /> : null}
    </>
  );
}
