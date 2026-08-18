import { useEffect, useState } from "react";
import type { GraphEdge, GraphPayload, ServiceRow } from "./contracts";
import { loadLocal, type LoadState } from "./dataSource";
import { presentBcEvidence, presentPeriodDiffs } from "./evidencePresentation";
import { roleLabel } from "./labels";

const LANE_DEFAULT = 10;
const LANE_MAX = 20;
const EDGE_DEFAULT = 10;
const EDGE_MAX = 20;
const MISSING_NAME = "표시명 없음";

const display = (value: string | null) => value ?? "검증된 값 없음";

function companyLabel(graph: GraphPayload, entityId: string) {
  const name = graph.nodes.find((node) => node.entity_id === entityId)?.display_name?.trim();
  return name ? name : MISSING_NAME;
}

function EdgeDetail({ graph, edge }: { graph: GraphPayload; edge: GraphEdge }) {
  return (
    <aside className="edge-detail">
      <h3>선택한 거래 관계 상세</h3>
      <p>{companyLabel(graph, edge.src_company_id)} → {companyLabel(graph, edge.dst_company_id)}</p>
      <dl>
        <div><dt>거래 건수</dt><dd>{edge.tx_count}</dd></div>
        <div><dt>고유 품목 수</dt><dd>{edge.unique_product_count}</dd></div>
        <div><dt>활성 월 수</dt><dd>{edge.active_month_count}</dd></div>
        <div><dt>금액 / 유효 건수 / coverage</dt><dd>{display(edge.amount_sum_clean)} / {edge.amount_valid_row_count} / {display(edge.amount_valid_rate)}</dd></div>
        <div><dt>원시 공급수량 / 유효 건수 / coverage</dt><dd>{display(edge.raw_supply_qty_sum)} / {edge.raw_supply_qty_valid_row_count} / {display(edge.raw_supply_qty_valid_rate)}</dd></div>
        <div><dt>낱개수량 / 유효 건수 / coverage</dt><dd>{display(edge.piece_qty_sum)} / {edge.piece_qty_valid_row_count} / {display(edge.piece_qty_valid_rate)}</dd></div>
      </dl>
    </aside>
  );
}

function Header({ label, anchor, months, status }: { label: string; anchor: string; months: string[]; status: string }) {
  return (
    <>
      <header className="hero">
        <p className="eyebrow">NIDS · CLASS 1</p>
        <h1>내부 거래 관계 모니터링</h1>
        <p>로컬 분석 데이터 · 내부 전용 · 공개 정책 미적용</p>
      </header>
      <section className="status">
        <strong>선택 업체</strong>
        <span className="id">{label}</span>
        <span>앵커월 {anchor} · 분석 구간 {months.join(" ~ ")}</span>
        <span>상태: {status}</span>
      </section>
    </>
  );
}

function incidentTx(graph: GraphPayload, selectedId: string, nodeId: string, direction: "in" | "out") {
  return graph.edges
    .filter((edge) => direction === "in"
      ? edge.src_company_id === nodeId && edge.dst_company_id === selectedId
      : edge.src_company_id === selectedId && edge.dst_company_id === nodeId)
    .reduce((sum, edge) => sum + edge.tx_count, 0);
}

function rankedLane(graph: GraphPayload, selectedId: string, direction: "in" | "out") {
  return graph.nodes
    .filter((node) => !node.selected && graph.edges.some((edge) => direction === "in"
      ? edge.src_company_id === node.entity_id && edge.dst_company_id === selectedId
      : edge.src_company_id === selectedId && edge.dst_company_id === node.entity_id))
    .map((node) => ({ node, tx: incidentTx(graph, selectedId, node.entity_id, direction) }))
    .sort((a, b) => b.tx - a.tx || a.node.entity_id.localeCompare(b.node.entity_id));
}

function truncate<T>(items: T[], limit: number) {
  return { visible: items.slice(0, limit), rest: Math.max(0, items.length - limit) };
}

function Lane({ title, empty, items, limit, onExpand }: {
  title: string;
  empty: string;
  items: Array<{ node: GraphPayload["nodes"][number]; tx: number }>;
  limit: number;
  onExpand?: () => void;
}) {
  const { visible, rest } = truncate(items, limit);
  return (
    <div className="lane">
      <h3>{title}</h3>
      {items.length === 0 ? <p className="lane-empty">{empty}</p> : visible.map(({ node, tx }) => (
        <span className="node" key={node.entity_id}>
          {node.display_name?.trim() ? node.display_name : MISSING_NAME}
          <small>{roleLabel(node.role_group)} · {tx}건</small>
        </span>
      ))}
      {rest > 0 ? <span className="node is-rest">기타 {rest}개</span> : null}
      {onExpand && rest > 0 && limit < LANE_MAX ? <button type="button" className="lane-more" onClick={onExpand}>더 보기 (최대 {LANE_MAX}개)</button> : null}
    </div>
  );
}

function Ready({ state, footer, hideHeader }: { state: Extract<LoadState, { kind: "ready" }>; footer?: string; hideHeader?: boolean }) {
  const { graph, service } = state;
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(graph.edges[0] ?? null);
  const [laneLimit, setLaneLimit] = useState(LANE_DEFAULT);
  const [edgeLimit, setEdgeLimit] = useState(EDGE_DEFAULT);
  if (service.run_status === "insufficient_graph") {
    return (
      <main id="main-content" className="shell" tabIndex={-1}>
        {hideHeader ? null : <Header label={companyLabel(graph, graph.selected_entity_id)} anchor={graph.anchor_month} months={graph.window_months} status={service.run_status} />}
        <section className="empty-state">
          <h2>관계망이 충분하지 않습니다</h2>
          <p>정상 local 분석 산출물에는 모델 점수와 service 결과가 없으므로 score-free 안내만 표시합니다.</p>
          <p>다른 업체를 보려면 offline runner를 해당 업체 ID로 다시 실행하십시오.</p>
        </section>
      </main>
    );
  }
  const row = service.service_results.find((item: ServiceRow) => item.entity_id === graph.selected_entity_id)!;
  const inbound = rankedLane(graph, row.entity_id, "in");
  const outbound = rankedLane(graph, row.entity_id, "out");
  const rankedEdges = [...graph.edges].sort((a, b) => b.tx_count - a.tx_count || `${a.src_company_id}${a.dst_company_id}`.localeCompare(`${b.src_company_id}${b.dst_company_id}`));
  const shownEdges = truncate(rankedEdges, edgeLimit);
  const bc = presentBcEvidence(row.bc_evidence);
  const diffs = presentPeriodDiffs(row.previous_anchor_diff, row.prior_nonoverlap_3m_diff);
  const priority = row.insufficient_sample
    ? "역할군 표본 부족"
    : row.review_priority_percentile == null
      ? "역할군 백분위 없음"
      : `역할군 백분위 ${row.review_priority_percentile}`;
  return (
    <main id="main-content" className="shell" tabIndex={-1}>
      {hideHeader ? null : <Header label={companyLabel(graph, row.entity_id)} anchor={row.anchor_month} months={row.window_months} status={service.run_status} />}
      <section className="summary">
        <article>
          <h2>검토 우선순위</h2>
          <p>{priority}</p>
          <small>역할군 {roleLabel(row.role_group)} · 표본 {row.role_group_sample_size} · 해당 앵커월·해당 역할군 안의 상대 순위</small>
        </article>
        <article>
          <h2>관계망 범위</h2>
          <p>1-hop 직접 거래 관계</p>
          <small>공급 업체 {inbound.length} · 공급받은 업체 {outbound.length} · 거래처 {graph.graph_summary.one_hop_counterparty_count} · 거래 관계 {graph.graph_summary.edge_count}</small>
        </article>
      </section>
      <section className="details">
        <article>
          <h2>경로 통과 보조지표</h2>
          <p>{bc.headline}</p>
          <small>{bc.note}</small>
          <dl>
            {bc.rows.map((item) => (
              <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>
            ))}
          </dl>
        </article>
        <article>
          <h2>거래 관계·규모 변화</h2>
          <p>{diffs.headline}</p>
          <small>{diffs.note}</small>
          <dl>
            {diffs.rows.map((item) => (
              <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>
            ))}
          </dl>
        </article>
      </section>
      <section className="graph-section">
        <h2>선택 업체 중심 1-hop 관계망</h2>
        <p className="graph-legend">간선 두께 기준은 거래 건수입니다. 좌우 열은 거래 건수 내림차순입니다.</p>
        <div className="graph">
          <Lane title="공급 업체" empty="이 업체로 공급한 직접 거래처가 없습니다." items={inbound} limit={laneLimit} onExpand={() => setLaneLimit(LANE_MAX)} />
          <div className="lane selected">
            <h3>최초 선택 업체</h3>
            <span className="node is-selected">{companyLabel(graph, row.entity_id)}<small>{roleLabel(row.role_group)}</small></span>
          </div>
          <Lane title="공급받은 업체" empty="이 업체가 공급한 직접 거래처가 없습니다." items={outbound} limit={laneLimit} onExpand={() => setLaneLimit(LANE_MAX)} />
        </div>
        <ul className="edge-list">
          {shownEdges.visible.map((edge) => (
            <li key={`${edge.src_company_id}-${edge.dst_company_id}`}>
              <button type="button" onClick={() => setSelectedEdge(edge)}>{companyLabel(graph, edge.src_company_id)} → {companyLabel(graph, edge.dst_company_id)} · {edge.tx_count}건</button>
            </li>
          ))}
          {shownEdges.rest > 0 ? <li className="edge-rest">기타 {shownEdges.rest}개</li> : null}
        </ul>
        {shownEdges.rest > 0 && edgeLimit < EDGE_MAX ? <button type="button" className="lane-more" onClick={() => setEdgeLimit(EDGE_MAX)}>거래 관계 더 보기 (최대 {EDGE_MAX}개)</button> : null}
        {selectedEdge && <EdgeDetail graph={graph} edge={selectedEdge} />}
      </section>
      <footer>{footer ?? "다른 업체를 보려면 offline runner를 해당 업체 ID로 다시 실행하십시오."}</footer>
    </main>
  );
}

export { Ready };
export default function App() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  useEffect(() => { void loadLocal().then(setState); }, []);
  return (
    <>
      <a className="skip" href="#main-content">본문으로 건너뛰기</a>
      {state.kind === "loading" ? <main className="shell"><p>로컬 분석 데이터를 준비하는 중입니다.</p></main>
        : state.kind === "error" ? <main id="main-content" className="shell empty-state" tabIndex={-1}><h1>내부 분석 데이터를 표시할 수 없습니다</h1><p>{state.message}</p></main>
        : <Ready state={state} />}
    </>
  );
}
