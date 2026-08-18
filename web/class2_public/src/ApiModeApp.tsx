import { useEffect, useMemo, useState } from "react";
import ComparisonResults from "./comparison/ComparisonResults";
import { presentComparison, selectionLabel } from "./comparison/presentation";
import type {
  ApiAnalysisAdapter,
  ApiCatalogItem,
  ApiComparisonView,
  ApiSelection,
  ApiStatus,
} from "./dataSource/apiAnalysisAdapter";

interface Props {
  adapter: ApiAnalysisAdapter;
  status: ApiStatus;
}

const monthInput = (value: string) => `${value.slice(0, 4)}-${value.slice(4)}`;
const monthPayload = (value: string) => value.replace("-", "");
function monthSpan(start: string, end: string): number {
  return (Number(end.slice(0, 4)) - Number(start.slice(0, 4))) * 12
    + Number(end.slice(4)) - Number(start.slice(4)) + 1;
}
function clampVisiblePeriod(periodStart: string, periodEnd: string, maxMonths = 36): { start: string; end: string } {
  if (monthSpan(periodStart, periodEnd) <= maxMonths) {
    return { start: monthInput(periodStart), end: monthInput(periodEnd) };
  }
  const endYear = Number(periodEnd.slice(0, 4));
  const endMonth = Number(periodEnd.slice(4));
  let year = endYear;
  let month = endMonth - (maxMonths - 1);
  while (month <= 0) {
    month += 12;
    year -= 1;
  }
  return { start: `${year}-${String(month).padStart(2, "0")}`, end: monthInput(periodEnd) };
}
const selectionTypeLabels = {
  item_group: "품목군",
  item_name: "품목명",
} as const;

const PREVIEW_LIMIT = 5;
const SEARCH_LIMIT = 20;
const initialMessage = "로컬 내부 API가 연결되었습니다. 공개 정책은 적용되지 않았습니다.";

function CatalogPicker({
  inputId,
  label,
  placeholder,
  query,
  onQueryChange,
  items,
  itemKey,
  itemText,
  typeLabel,
  listLabel,
  onPick,
}: {
  inputId: string;
  label: string;
  placeholder: string;
  query: string;
  onQueryChange: (value: string) => void;
  items: ApiCatalogItem[];
  itemKey: (item: ApiCatalogItem) => string;
  itemText: (item: ApiCatalogItem) => string;
  typeLabel: string;
  listLabel: string;
  onPick: (item: ApiCatalogItem) => void;
}) {
  const [open, setOpen] = useState(false);
  const preview = items.slice(0, PREVIEW_LIMIT);
  const list = items.slice(0, SEARCH_LIMIT);

  return (
    <div className="catalog-picker">
      <label className="search-label" htmlFor={inputId}>
        {label}
        <input
          id={inputId}
          type="search"
          value={query}
          placeholder={placeholder}
          autoComplete="off"
          aria-expanded={open}
          aria-controls={`${inputId}-results`}
          onChange={(event) => onQueryChange(event.target.value)}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
        />
      </label>
      {open ? (
        <ul
          id={`${inputId}-results`}
          className="search-results is-scroll"
          aria-label={listLabel}
          onMouseDown={(event) => event.preventDefault()}
        >
          {list.length ? list.map((item) => (
            <li key={itemKey(item)}>
              <button
                type="button"
                className="search-result-button"
                onClick={() => onPick(item)}
              >
                <span className="type-badge">{typeLabel}</span>
                {" "}
                <span className="synthetic-label">{itemText(item)}</span>
              </button>
            </li>
          )) : (
            <li className="search-empty" role="status">일치하는 품목이 없습니다.</li>
          )}
        </ul>
      ) : (
        <ul className="catalog-preview" aria-label={`${label} 미리보기`}>
          {preview.map((item) => (
            <li key={itemKey(item)}>
              <button type="button" className="catalog-card" onClick={() => onPick(item)}>
                <span className="type-badge">{typeLabel}</span>
                {" "}
                <span className="catalog-card__name">{itemText(item)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ApiModeApp({ adapter, status }: Props) {
  const [groupQuery, setGroupQuery] = useState("");
  const [groups, setGroups] = useState<ApiCatalogItem[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [nameQuery, setNameQuery] = useState("");
  const [names, setNames] = useState<ApiCatalogItem[]>([]);
  const [selections, setSelections] = useState<ApiSelection[]>([]);
  const [start, setStart] = useState(() => clampVisiblePeriod(status.period_start, status.period_end).start);
  const [end, setEnd] = useState(() => clampVisiblePeriod(status.period_start, status.period_end).end);
  const [view, setView] = useState<ApiComparisonView | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error" | "policy_pending" | "empty">("policy_pending");
  const [message, setMessage] = useState(initialMessage);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void adapter.itemGroups(groupQuery, SEARCH_LIMIT).then(setGroups).catch(() => {
        setState("error");
        setMessage("품목군 목록을 불러오지 못했습니다.");
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [adapter, groupQuery]);

  useEffect(() => {
    if (!selectedGroup) {
      setNames([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void adapter.itemNames(selectedGroup, nameQuery, SEARCH_LIMIT).then(setNames).catch(() => {
        setState("error");
        setMessage("선택한 품목군 안의 품목명 목록을 불러오지 못했습니다.");
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [adapter, selectedGroup, nameQuery]);

  const invalidPeriod = !start || !end || start > end
    || ((Number(end.slice(0, 4)) - Number(start.slice(0, 4))) * 12 + Number(end.slice(5)) - Number(start.slice(5)) + 1 > 36);
  const canRun = selections.length > 0 && selections.length <= 10 && !invalidPeriod;
  const selectedKeys = useMemo(
    () => new Set(selections.map((item) => `${item.selection_type}:${item.item_group_id}:${item.item_name_id ?? ""}`)),
    [selections],
  );

  function add(selection: ApiSelection) {
    const key = `${selection.selection_type}:${selection.item_group_id}:${selection.item_name_id ?? ""}`;
    if (!selectedKeys.has(key) && selections.length < 10) {
      setSelections((current) => [...current, selection]);
    }
  }

  async function run(): Promise<void> {
    if (!canRun) return;
    setState("loading");
    setMessage("검증된 로컬 집계 관측값을 불러오는 중입니다.");
    try {
      const next = await adapter.compare(monthPayload(start), monthPayload(end), selections);
      const hasRows = presentComparison(next).hasRows;
      setView(next);
      setState(hasRows ? "idle" : "empty");
      setMessage(
        hasRows
          ? "로컬 집계 비교를 불러왔습니다. 공개 정책은 적용되지 않았습니다."
          : "선택한 품목과 기간에 맞는 집계 관측값이 없습니다.",
      );
    } catch {
      setState("error");
      setMessage("비교 요청이 실패했거나 로컬 API가 거부했습니다.");
    }
  }

  return (
    <>
      <a className="skip-link" href="#main-content">본문 바로가기</a>

      <main id="main-content" className="app-shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">품목 비교 분석</p>
          <h1>품목 비교분석</h1>
          <p className="hero-lead">
            고른 품목군·품목명의 보고 거래 활동을 품목별로 나란히 보는 화면입니다.
          </p>
          <p className="data-boundary" role="note">
            로컬 내부 API는 공개 정책이 적용되지 않은 상태입니다. 공급 활동을
            판매량·수요·시장 성장으로 해석하지 않습니다.
          </p>
        </header>

        <div className={`state-notice state-${state === "error" ? "danger" : "attention"}`} role="status" aria-live="polite">
          <strong>현재 화면 상태</strong>
          <span>{message}</span>
        </div>

        <section className="search-panel" aria-labelledby="api-search-heading">
          <div className="section-heading">
            <p className="section-kicker">비교 조건</p>
            <h2 id="api-search-heading">품목군·품목명 검색</h2>
          </div>
          <p className="placeholder-note">
            기본으로 5개 품목을 카드로 보여 줍니다. 검색창을 누르면 최대 20개를 스크롤할 수 있습니다.
          </p>
          <CatalogPicker
            inputId="item-group-search"
            label="품목군 검색"
            placeholder="품목군을 검색하는 영역"
            query={groupQuery}
            onQueryChange={setGroupQuery}
            items={groups}
            itemKey={(item) => item.item_group_id}
            itemText={(item) => item.item_group_id}
            typeLabel={selectionTypeLabels.item_group}
            listLabel="품목군 검색 결과"
            onPick={(item) => {
              setSelectedGroup(item.item_group_id);
              add({ selection_type: "item_group", item_group_id: item.item_group_id });
            }}
          />
          {selectedGroup && (
            <CatalogPicker
              inputId="item-name-search"
              label={`${selectedGroup} 안의 품목명 검색`}
              placeholder="선택한 품목군 안에서 품목명을 검색합니다"
              query={nameQuery}
              onQueryChange={setNameQuery}
              items={names}
              itemKey={(item) => item.item_name_id ?? item.item_group_id}
              itemText={(item) => item.item_name_id ?? item.item_group_id}
              typeLabel={selectionTypeLabels.item_name}
              listLabel="품목명 검색 결과"
              onPick={(item) => add({
                selection_type: "item_name",
                item_group_id: selectedGroup,
                item_name_id: item.item_name_id,
              })}
            />
          )}
        </section>

        <div className="filter-strip">
          <section className="selection-panel" aria-labelledby="selection-heading">
            <h2 id="selection-heading">선택 품목 ({selections.length}/10)</h2>
            {selections.length ? (
              <ul className="selection-list">
                {selections.map((item) => (
                  <li key={`${item.selection_type}:${selectionLabel(item)}`}>
                    <span className="type-badge">{selectionTypeLabels[item.selection_type]}</span>
                    <span className="synthetic-label">{selectionLabel(item)}</span>
                    <button
                      type="button"
                      className="remove-selection"
                      onClick={() => setSelections((current) => current.filter((entry) => entry !== item))}
                      aria-label={`${selectionLabel(item)} 선택 제거`}
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
                <input type="month" value={start} onChange={(event) => setStart(event.target.value)} />
              </label>
              <label>
                종료 월
                <input type="month" value={end} onChange={(event) => setEnd(event.target.value)} />
              </label>
            </div>
            {invalidPeriod && (
              <p className="field-error" role="alert">
                시작 월은 종료 월보다 늦을 수 없으며, 기간은 36개월을 넘을 수 없습니다.
              </p>
            )}
            <button
              type="button"
              className="period-apply"
              disabled={!canRun || state === "loading"}
              onClick={() => void run()}
            >
              비교 실행
            </button>
          </section>
        </div>

        {view && <ComparisonResults view={view} />}
      </main>
    </>
  );
}
