import { useMemo, useState } from "react";
import type { ApiComparisonView } from "../dataSource/apiAnalysisAdapter";
import TrendChart, { seriesColor } from "./TrendChart";
import {
  displayCount,
  displayDecimal,
  displayDeltaShort,
  displayHhi,
  displayMissingMonths,
  displayMix,
  displayMonth,
  displayMonthSpan,
  displayPeriodChange,
  displayPrimaryMix,
  displayRate,
  displayRegions,
  filterProducts,
  presentComparison,
  type TrendMetric,
} from "./presentation";

const selectionTypeLabels = {
  item_group: "품목군",
  item_name: "품목명",
} as const;

export default function ComparisonResults({ view }: { view: ApiComparisonView }) {
  const presentation = useMemo(() => presentComparison(view), [view]);
  const [metric, setMetric] = useState<TrendMetric>("tx_count");
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [productQuery, setProductQuery] = useState("");

  return (
    <>
      <section className="query-summary" aria-labelledby="query-heading">
        <div className="section-heading section-heading--rule">
          <p className="section-kicker">이번 조회</p>
          <h2 id="query-heading">선택 조건 요약</h2>
        </div>
        <dl className="released-content">
          <div>
            <dt>선택 품목</dt>
            <dd>
              <ul className="query-selections">
                {presentation.query.selections.map((selection) => (
                  <li key={`${selection.type}:${selection.label}`}>
                    <span className="type-badge">{selectionTypeLabels[selection.type]}</span>
                    {selection.label}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
          <div>
            <dt>요청 기간</dt>
            <dd>
              {displayMonth(presentation.query.period_start)} ~ {displayMonth(presentation.query.period_end)}
            </dd>
          </div>
          <div>
            <dt>선택 품목 포함 월</dt>
            <dd>{displayMonthSpan(presentation.query.included_months)}</dd>
          </div>
          <div>
            <dt>선택 품목 누락 월</dt>
            <dd>{displayMissingMonths(presentation.query.missing_months)}</dd>
          </div>
        </dl>
      </section>

      {!presentation.hasRows ? (
        <p className="empty-copy empty-copy--prominent">조건에 맞는 결과가 없습니다.</p>
      ) : (
      <>
      <section className="results-section" aria-labelledby="comparison-heading">
        <div className="section-heading section-heading--rule">
          <p className="section-kicker">품목 비교</p>
          <h2 id="comparison-heading">선택한 품목 비교</h2>
        </div>
        <p className="placeholder-note">
          아래 표는 기간 첫 달과 최근 달의 보고 거래 건수를 나란히 봅니다. 카드는 그 품목의
          최근 달 구조입니다. 기간 합계는 유통 단계 중첩을 지우지 않으므로 기본 비교에 두지
          않으며, 증가를 수요·시장 성장으로 해석하지 않습니다. 공급 집중도는 최근 월 × 이
          선택 품목의 거래 건수 비중 제곱합(0–10,000)이며 품목끼리 합치지 않습니다.
        </p>
        <div className="compare-table-wrap">
          <table className="compare-table">
            <caption className="visually-hidden">선택한 품목의 기간 초 대비 최근 월 보고 거래</caption>
            <thead>
              <tr>
                <th scope="col">선택 품목</th>
                <th scope="col">최근 월 거래</th>
                <th scope="col">기간 초 대비</th>
                <th scope="col">공급 집중도</th>
                <th scope="col">주요 수령 역할</th>
              </tr>
            </thead>
            <tbody>
              {presentation.summaries.map((summary, index) => (
                <tr key={summary.key}>
                  <th scope="row">
                    <span className="trend-legend__swatch" style={{ background: seriesColor(index) }} />
                    {selectionTypeLabels[summary.selection.selection_type]} · {summary.label}
                  </th>
                  <td>
                    {summary.period_change
                      ? `${displayMonth(summary.period_change.end_month)} ${displayCount(summary.period_change.tx_to)}건`
                      : `${displayCount(summary.median_tx_count)}건(중앙값)`}
                  </td>
                  <td>
                    {summary.period_change
                      ? displayDeltaShort(summary.period_change.tx_from, summary.period_change.tx_to, "건")
                      : "비교 월 부족"}
                  </td>
                  <td>{displayHhi(summary.supplier_hhi_tx)}</td>
                  <td>{displayPrimaryMix(summary.receiver_mix_tx.length ? summary.receiver_mix_tx : summary.receiver_mix)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card-grid">
          {presentation.summaries.map((summary, index) => {
            const open = openKey === summary.key;
            const products = filterProducts(summary.products, open ? productQuery : "");
            return (
              <article className={`result-card${open ? " is-open" : ""}`} key={summary.key}>
                <div className="result-card__header">
                  <h3>
                    <span className="trend-legend__swatch" style={{ background: seriesColor(index) }} />
                    {selectionTypeLabels[summary.selection.selection_type]} · {summary.label}
                  </h3>
                  <span className="status-chip">{summary.month_count}개월</span>
                </div>
                {summary.period_change ? (
                  <p className="change-lead">
                    {displayPeriodChange(
                      summary.period_change.start_month,
                      summary.period_change.end_month,
                      summary.period_change.tx_from,
                      summary.period_change.tx_to,
                      "건",
                    )}
                  </p>
                ) : (
                  <p className="change-lead">기간 초와 최근 월을 나란히 비교할 월이 부족합니다.</p>
                )}
                <dl className="released-content">
                  <div><dt>월 거래 건수 중앙값</dt><dd>{displayCount(summary.median_tx_count)}</dd></div>
                  {summary.period_change ? (
                    <>
                      <div>
                        <dt>공급자 수 변화</dt>
                        <dd>{displayPeriodChange(summary.period_change.start_month, summary.period_change.end_month, summary.period_change.supplier_from, summary.period_change.supplier_to, "곳")}</dd>
                      </div>
                      <div>
                        <dt>수령자 수 변화</dt>
                        <dd>{displayPeriodChange(summary.period_change.start_month, summary.period_change.end_month, summary.period_change.receiver_from, summary.period_change.receiver_to, "곳")}</dd>
                      </div>
                    </>
                  ) : null}
                  <div><dt>공급 집중도 (최근 월)</dt><dd>{displayHhi(summary.supplier_hhi_tx)}</dd></div>
                  <div><dt>수령 역할 (최근 월, 수령자 수)</dt><dd>{displayMix(summary.receiver_mix)}</dd></div>
                  <div><dt>수령 역할 (최근 월, 거래 건수)</dt><dd>{displayMix(summary.receiver_mix_tx)}</dd></div>
                  <div><dt>수령 광역 (최근 월)</dt><dd>{displayRegions(summary.region_names)}</dd></div>
                  <div><dt>금액 유효률</dt><dd>{displayRate(summary.amount_valid_rate)}</dd></div>
                  <div><dt>수량 유효률</dt><dd>{displayRate(summary.qty_valid_rate)}</dd></div>
                  <div><dt>최근 월 공급자 수</dt><dd>{displayCount(summary.latest_supplier_count)}</dd></div>
                  <div><dt>최근 월 수령자 수</dt><dd>{displayCount(summary.latest_receiver_count)}</dd></div>
                </dl>
                <button
                  type="button"
                  className="detail-toggle"
                  aria-expanded={open}
                  onClick={() => {
                    setOpenKey(open ? null : summary.key);
                    setProductQuery("");
                  }}
                >
                  {open ? "상위 품목·구성 닫기" : "상위 품목·구성 보기"}
                </button>
                {open && (
                  <div className="result-detail">
                    <p className="placeholder-note">
                      거래 건수 기준 상위 {Math.min(5, summary.products.length)}개 품목을 보여 줍니다.
                      아래 기간 합계는 보고된 유통 활동이며 수요·시장 규모가 아닙니다.
                    </p>
                    <dl className="released-content">
                      <div><dt>기간 거래 건수</dt><dd>{displayCount(summary.tx_count)}</dd></div>
                      <div><dt>기간 공급금액</dt><dd>{displayDecimal(summary.amount_sum_clean)}</dd></div>
                      <div><dt>원시 공급수량</dt><dd>{displayDecimal(summary.raw_supply_qty_sum)}</dd></div>
                      <div><dt>낱개수량 (검증됨)</dt><dd>{displayDecimal(summary.piece_qty_sum)}</dd></div>
                    </dl>
                    <label className="search-label">
                      이 선택 안 품목 검색
                      <input
                        type="search"
                        value={productQuery}
                        onChange={(event) => setProductQuery(event.target.value)}
                        placeholder="품목명으로 검색"
                        autoComplete="off"
                      />
                    </label>
                    {products.length ? (
                      <ul className="composition-list">
                        {products.map((item) => (
                          <li key={item.product_id}>
                            <span>{item.item_name_id}</span>
                            <span>거래 {displayCount(item.tx_count)}건 · 공급금액 {displayDecimal(item.amount_sum_clean)}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="empty-copy">검색과 맞는 상위 품목이 없습니다.</p>
                    )}
                    {summary.latest_month && summary.composition.length > 0 && (
                      <>
                        <h4>{displayMonth(summary.latest_month)} 관측 구성 (상위)</h4>
                        <ul className="reach-list">
                          {summary.composition.map((item) => (
                            <li key={`${item.dimension}:${item.dimension_value}`}>
                              <span>{item.dimension}</span>
                              <span>{item.dimension_value} · {displayCount(item.entity_count_distinct)}</span>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section className="trend-section" aria-labelledby="trend-heading">
        <div className="section-heading">
          <p className="section-kicker">기간별 보기</p>
          <h2 id="trend-heading">월별 추세</h2>
        </div>
        <div className="metric-toggle" role="group" aria-label="추세 지표">
          <button type="button" className={metric === "tx_count" ? "is-active" : ""} onClick={() => setMetric("tx_count")}>
            거래 건수
          </button>
          <button type="button" className={metric === "amount_sum_clean" ? "is-active" : ""} onClick={() => setMetric("amount_sum_clean")}>
            공급금액
          </button>
        </div>
        <TrendChart
          metric={metric}
          series={presentation.summaries.map((summary) => ({
            key: summary.key,
            label: summary.label,
            points: summary.series,
          }))}
        />
        <p className="placeholder-note">월별 보고 거래 활동입니다. 증가를 수요 증가나 시장 성장으로 단정하지 않습니다.</p>
      </section>

      <section className="portfolio-panel" aria-labelledby="portfolio-heading">
        <div className="section-heading">
          <p className="section-kicker">구성 요약</p>
          <h2 id="portfolio-heading">선택 포트폴리오 요약</h2>
        </div>
        <p className="placeholder-note">
          고른 품목의 거래 활동 비중과 기간 안 거래처 합집합·겹침입니다. 개별 품목 카드를 대체하지
          않으며, 품목별 HHI를 합치지 않습니다. 낱개 수량 비중은 단위가 확인되지 않아 표시하지 않습니다.
        </p>
        <ul className="composition-list">
          {presentation.portfolio.shares.map((item) => (
            <li key={item.key}>
              <span>{item.label}</span>
              <span>거래 {displayCount(item.tx_count)}건 · 선택 내 비중 {displayRate(item.tx_share)}</span>
            </li>
          ))}
        </ul>
        <dl className="released-content">
          <div><dt>공급자 합집합</dt><dd>{displayCount(presentation.portfolio.supplier_union_count)}</dd></div>
          <div><dt>수령자 합집합</dt><dd>{displayCount(presentation.portfolio.receiver_union_count)}</dd></div>
          <div><dt>금액 유효률 (거래 가중)</dt><dd>{displayRate(presentation.portfolio.amount_valid_rate)}</dd></div>
          <div><dt>수량 유효률 (거래 가중)</dt><dd>{displayRate(presentation.portfolio.qty_valid_rate)}</dd></div>
        </dl>
        {presentation.portfolio.pairs.length > 0 && (
          <ul className="reach-list">
            {presentation.portfolio.pairs.map((pair) => (
              <li key={`${pair.left}:${pair.right}`}>
                <span>{pair.left} ∩ {pair.right}</span>
                <span>공급자 {displayCount(pair.supplier_intersection_count)} · 수령자 {displayCount(pair.receiver_intersection_count)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      </>
      )}

      <section className="coverage-section" aria-labelledby="coverage-heading">
        <div className="section-heading">
          <p className="section-kicker">공개 범위 확인</p>
          <h2 id="coverage-heading">데이터 coverage·결측·억제 안내</h2>
        </div>
        <p className="placeholder-note">
          이 실행은 공개 억제를 적용하지 않았습니다. 값은 숨기지 않으며, 도달 구조는 집계
          차원입니다. 원본 공급자·수령자 식별자는 표시하지 않습니다.
        </p>
        <dl className="released-content">
          <div>
            <dt>요청 월</dt>
            <dd>{displayMonthSpan(presentation.coverage.requested_months)}</dd>
          </div>
          <div>
            <dt>마트에 있는 월</dt>
            <dd>{displayMonthSpan(presentation.coverage.included_months)}</dd>
          </div>
          <div>
            <dt>마트에 없는 월</dt>
            <dd>{displayMissingMonths(presentation.coverage.missing_months)}</dd>
          </div>
          <div>
            <dt>관측 건수</dt>
            <dd>{displayCount(presentation.coverage.observation_count)}</dd>
          </div>
          <div>
            <dt>공개 억제</dt>
            <dd>미적용</dd>
          </div>
        </dl>
      </section>
    </>
  );
}
