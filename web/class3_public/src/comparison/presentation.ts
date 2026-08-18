import type { ApiComparisonView, ApiSelection } from "../dataSource/apiAnalysisAdapter";

export const TOP_PRODUCT_LIMIT = 5;
export const TOP_COMPOSITION_LIMIT = 5;
export const PRODUCT_SEARCH_LIMIT = 20;

export type TrendMetric = "tx_count" | "amount_sum_clean";

export interface MonthlyPoint {
  month: string;
  tx_count: number | null;
  amount_sum_clean: string | null;
  supplier_count: number | null;
  receiver_count: number | null;
  amount_valid_row_count: number | null;
  raw_supply_qty_valid_row_count: number | null;
}

export interface RankedProduct {
  product_id: string;
  item_name_id: string;
  tx_count: number;
  amount_sum_clean: string | null;
}

export interface CompositionSlice {
  dimension: string;
  dimension_value: string;
  entity_count_distinct: number;
}

export interface MixShare {
  label: string;
  count: number;
  share: number;
}

export interface PeriodChange {
  start_month: string;
  end_month: string;
  tx_from: number | null;
  tx_to: number | null;
  supplier_from: number | null;
  supplier_to: number | null;
  receiver_from: number | null;
  receiver_to: number | null;
}

export interface SelectionSummary {
  key: string;
  selection: ApiSelection;
  label: string;
  month_count: number;
  median_tx_count: number | null;
  tx_count: number | null;
  amount_sum_clean: string | null;
  raw_supply_qty_sum: string | null;
  piece_qty_sum: string | null;
  latest_supplier_count: number | null;
  latest_receiver_count: number | null;
  amount_valid_rate: number | null;
  qty_valid_rate: number | null;
  supplier_hhi_tx: string | null;
  receiver_mix: MixShare[];
  receiver_mix_tx: MixShare[];
  region_names: string[];
  series: MonthlyPoint[];
  products: RankedProduct[];
  latest_month: string | null;
  composition: CompositionSlice[];
  period_change: PeriodChange | null;
}

export interface QuerySelection {
  type: ApiSelection["selection_type"];
  label: string;
}

export interface QueryDigest {
  selections: QuerySelection[];
  period_start: string;
  period_end: string;
  included_months: string[];
  missing_months: string[];
}

export interface CoverageDigest {
  requested_months: string[];
  included_months: string[];
  missing_months: string[];
  observation_count: number | null;
}

export interface PortfolioShare {
  key: string;
  label: string;
  tx_count: number | null;
  tx_share: number | null;
}

export interface PortfolioPair {
  left: string;
  right: string;
  supplier_intersection_count: number | null;
  receiver_intersection_count: number | null;
}

export interface PortfolioDigest {
  shares: PortfolioShare[];
  amount_valid_rate: number | null;
  qty_valid_rate: number | null;
  supplier_union_count: number | null;
  receiver_union_count: number | null;
  pairs: PortfolioPair[];
}

export interface ComparisonPresentation {
  query: QueryDigest;
  summaries: SelectionSummary[];
  portfolio: PortfolioDigest;
  coverage: CoverageDigest;
  hasRows: boolean;
}

export function selectionKey(selection: ApiSelection): string {
  return selection.selection_type === "item_name"
    ? `item_name:${selection.item_group_id}:${selection.item_name_id ?? ""}`
    : `item_group:${selection.item_group_id}`;
}

export function selectionLabel(selection: ApiSelection): string {
  return selection.item_name_id
    ? `${selection.item_group_id} / ${selection.item_name_id}`
    : selection.item_group_id;
}

export function displayMonth(month: string): string {
  return /^\d{6}$/.test(month) ? `${month.slice(0, 4)}-${month.slice(4)}` : month;
}

export function displayCount(value: number | null): string {
  return value == null ? "없음" : value.toLocaleString("ko-KR");
}

export function displayDecimal(value: string | null): string {
  if (value == null || value.trim() === "") return "없음";
  const trimmed = value.trim();
  if (!/^(-?)(\d+)(?:\.(\d+))?$/.test(trimmed)) return "없음";
  const micro = toMicro(trimmed);
  const sign = micro < 0n ? "-" : "";
  const abs = micro < 0n ? -micro : micro;
  const whole = (abs / 1_000_000n).toLocaleString("ko-KR");
  const fraction = abs % 1_000_000n;
  if (fraction === 0n) return `${sign}${whole}`;
  return `${sign}${whole}.${fraction.toString().padStart(6, "0").replace(/0+$/, "")}`;
}

export function displayRate(value: number | null): string {
  return value == null ? "없음" : `${Math.round(value * 100)}%`;
}

export function displayHhi(value: string | null): string {
  if (value == null || value.trim() === "") return "없음";
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) return "없음";
  return Math.round(numeric * 10_000).toLocaleString("ko-KR");
}

export function displayMix(shares: MixShare[]): string {
  return shares.length ? shares.map((item) => `${item.label} ${displayRate(item.share)}`).join(" · ") : "없음";
}

export function displayPrimaryMix(shares: MixShare[]): string {
  return shares[0] ? `${shares[0].label} ${displayRate(shares[0].share)}` : "없음";
}

export function displayDeltaShort(from: number | null, to: number | null, unit: string): string {
  if (from == null || to == null) return "비교 월 부족";
  const delta = to - from;
  if (delta === 0) return "변화 없음";
  return `${delta > 0 ? "+" : "-"}${Math.abs(delta).toLocaleString("ko-KR")}${unit}`;
}

export function displayPeriodChange(
  startMonth: string,
  endMonth: string,
  from: number | null,
  to: number | null,
  unit: string,
): string {
  if (from == null || to == null) return "기간 초와 최근 월을 나란히 비교할 수 없습니다.";
  const delta = to - from;
  const span = `${displayMonth(startMonth)} ${from.toLocaleString("ko-KR")}${unit} → ${displayMonth(endMonth)} ${to.toLocaleString("ko-KR")}${unit}`;
  if (delta === 0) return `${span} · 변화 없음`;
  return `${span} · ${Math.abs(delta).toLocaleString("ko-KR")}${unit} ${delta > 0 ? "증가" : "감소"}`;
}

export function displayRegions(names: string[]): string {
  if (!names.length) return "없음";
  if (names.length <= 2) return names.join(", ");
  return `${names.slice(0, 2).join(", ")} 외`;
}

export function monthsInPeriod(start: string, end: string): string[] {
  if (!/^\d{6}$/.test(start) || !/^\d{6}$/.test(end) || start > end) return [];
  const months: string[] = [];
  let year = Number(start.slice(0, 4));
  let month = Number(start.slice(4));
  const endYear = Number(end.slice(0, 4));
  const endMonth = Number(end.slice(4));
  while (year < endYear || (year === endYear && month <= endMonth)) {
    months.push(`${year}${String(month).padStart(2, "0")}`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return months;
}

export function displayMonthSpan(months: string[]): string {
  if (!months.length) return "없음";
  const first = months[0]!;
  const last = months.at(-1)!;
  if (months.length === 1) return displayMonth(first);
  if (monthsInPeriod(first, last).length === months.length) {
    return `${displayMonth(first)} ~ ${displayMonth(last)} (${months.length}개월)`;
  }
  if (months.length <= 6) return months.map(displayMonth).join(", ");
  return `${months.slice(0, 4).map(displayMonth).join(", ")} 외 ${months.length - 4}개월`;
}

export function displayMissingMonths(months: string[]): string {
  if (!months.length) return "없음";
  if (months.length <= 8) return months.map(displayMonth).join(", ");
  return `${months.slice(0, 6).map(displayMonth).join(", ")} 외 ${months.length - 6}개월`;
}

export function bucketReceiverType(value: string): "의료기관" | "유통" | "제조·수입" | "그 외" {
  const text = value.replace(/\s/g, "");
  if (/의료기관|병원|의원|요양/.test(text)) return "의료기관";
  if (/유통|도매|판매|임대/.test(text)) return "유통";
  if (/제조|수입/.test(text)) return "제조·수입";
  return "그 외";
}

export function presentComparison(view: ApiComparisonView): ComparisonPresentation {
  const catalog = view.product_catalog;
  const productMonth = view.product_month;
  const groupMonth = view.item_group_month;
  const summaries = view.selections.map((selection) => {
    const products = matchingCatalog(catalog, selection);
    const productIds = new Set(products.map((row) => text(row.product_id)));
    const monthly = selection.selection_type === "item_group"
      ? monthlyFromRows(groupMonth.filter((row) => text(row.item_group_id) === selection.item_group_id), true)
      : monthlyFromRows(productMonth.filter((row) => productIds.has(text(row.product_id))), productIds.size <= 1);
    const ranked = rankProducts(products, productMonth);
    const latest = monthly.at(-1) ?? null;
    const sourceRows = rowsForMonths(selection, groupMonth, productMonth, productIds);
    const txTotal = sumCounts(monthly.map((point) => point.tx_count));
    const mixRows = scopedComposition(view.endpoint_composition, selection, productIds, latest?.month ?? null);
    return {
      key: selectionKey(selection),
      selection,
      label: selectionLabel(selection),
      month_count: monthly.length,
      median_tx_count: median(monthly.map((point) => point.tx_count)),
      tx_count: txTotal,
      amount_sum_clean: sumDecimals(monthly.map((point) => point.amount_sum_clean)),
      raw_supply_qty_sum: sumDecimals(sourceRows.map((row) => asDecimal(row.raw_supply_qty_sum))),
      piece_qty_sum: sumDecimals(sourceRows.map((row) => asDecimal(row.piece_qty_sum))),
      latest_supplier_count: latest?.supplier_count ?? null,
      latest_receiver_count: latest?.receiver_count ?? null,
      amount_valid_rate: ratio(sumCounts(monthly.map((point) => point.amount_valid_row_count)), txTotal),
      qty_valid_rate: ratio(sumCounts(monthly.map((point) => point.raw_supply_qty_valid_row_count)), txTotal),
      supplier_hhi_tx: latestHhi(view.selection_concentration, selection, latest?.month ?? null),
      receiver_mix: receiverMix(mixRows, latest?.receiver_count ?? null, "entity_count_distinct"),
      receiver_mix_tx: receiverMix(mixRows, latest?.tx_count ?? null, "tx_count"),
      region_names: regionNames(mixRows),
      series: monthly,
      products: ranked,
      latest_month: latest?.month ?? null,
      composition: latestComposition(mixRows),
      period_change: periodChange(monthly),
    };
  });
  const requested = monthsInPeriod(view.period_start, view.period_end);
  const selectionMonths = new Set(summaries.flatMap((item) => item.series.map((point) => point.month)));
  const martMonths = new Set(view.coverage.map((row) => text(row.month)).filter(Boolean));
  const coverage = {
    requested_months: requested,
    included_months: requested.filter((month) => martMonths.has(month)),
    missing_months: requested.filter((month) => !martMonths.has(month)),
    observation_count: sumCounts(view.coverage.map((row) => asCount(row.aggregate_observation_count))),
  };
  const query = {
    selections: view.selections.map((selection) => ({
      type: selection.selection_type,
      label: selectionLabel(selection),
    })),
    period_start: view.period_start,
    period_end: view.period_end,
    included_months: requested.filter((month) => selectionMonths.has(month)),
    missing_months: requested.filter((month) => !selectionMonths.has(month)),
  };
  return { query, summaries, portfolio: presentPortfolio(view, summaries), coverage, hasRows: summaries.some((item) => item.month_count > 0) };
}

export function filterProducts(products: RankedProduct[], query: string): RankedProduct[] {
  const needle = query.trim().toLowerCase();
  const matched = needle
    ? products.filter((item) => item.item_name_id.toLowerCase().includes(needle) || item.product_id.toLowerCase().includes(needle))
    : products;
  return matched.slice(0, needle ? PRODUCT_SEARCH_LIMIT : TOP_PRODUCT_LIMIT);
}

export function seriesValue(point: MonthlyPoint, metric: TrendMetric): number | null {
  if (metric === "tx_count") return point.tx_count;
  if (point.amount_sum_clean == null) return null;
  const value = Number(point.amount_sum_clean);
  return Number.isFinite(value) ? value : null;
}

function latestHhi(
  rows: Array<Record<string, unknown>> | undefined,
  selection: ApiSelection,
  latestMonth: string | null,
): string | null {
  if (!latestMonth || !rows?.length) return null;
  const match = rows.find((row) => {
    if (text(row.month) !== latestMonth) return false;
    if (text(row.item_group_id) !== selection.item_group_id) return false;
    if (selection.selection_type === "item_name") {
      return text(row.selection_type) === "item_name" && text(row.item_name_id) === (selection.item_name_id ?? "");
    }
    return text(row.selection_type) === "item_group";
  });
  return match ? asDecimal(match.supplier_hhi_tx) : null;
}

function presentPortfolio(view: ApiComparisonView, summaries: SelectionSummary[]): PortfolioDigest {
  const overlap = view.portfolio_overlap ?? {};
  const txTotal = sumCounts(summaries.map((item) => item.tx_count));
  const pairs = Array.isArray(overlap.pairs) ? overlap.pairs : [];
  return {
    shares: summaries.map((item) => ({
      key: item.key,
      label: item.label,
      tx_count: item.tx_count,
      tx_share: ratio(item.tx_count, txTotal),
    })),
    amount_valid_rate: ratio(
      sumCounts(summaries.map((item) => ratioCount(item.amount_valid_rate, item.tx_count))),
      txTotal,
    ),
    qty_valid_rate: ratio(
      sumCounts(summaries.map((item) => ratioCount(item.qty_valid_rate, item.tx_count))),
      txTotal,
    ),
    supplier_union_count: asCount(overlap.supplier_union_count),
    receiver_union_count: asCount(overlap.receiver_union_count),
    pairs: pairs.map((entry) => {
      const row = entry && typeof entry === "object" && !Array.isArray(entry) ? entry as Record<string, unknown> : {};
      const left = row.left && typeof row.left === "object" && !Array.isArray(row.left) ? row.left as Record<string, unknown> : {};
      const right = row.right && typeof row.right === "object" && !Array.isArray(row.right) ? row.right as Record<string, unknown> : {};
      return {
        left: overlapLabel(left),
        right: overlapLabel(right),
        supplier_intersection_count: asCount(row.supplier_intersection_count),
        receiver_intersection_count: asCount(row.receiver_intersection_count),
      };
    }),
  };
}

function overlapLabel(row: Record<string, unknown>): string {
  const group = text(row.item_group_id);
  const name = text(row.item_name_id);
  return name ? `${group} / ${name}` : group || "선택";
}

function ratioCount(rate: number | null, total: number | null): number | null {
  if (rate == null || total == null) return null;
  return rate * total;
}

function matchingCatalog(catalog: Array<Record<string, unknown>>, selection: ApiSelection): Array<Record<string, unknown>> {
  return catalog.filter((row) => {
    if (text(row.item_group_id) !== selection.item_group_id) return false;
    return selection.selection_type === "item_group" || text(row.item_name_id) === (selection.item_name_id ?? "");
  });
}

function rowsForMonths(
  selection: ApiSelection,
  groupMonth: Array<Record<string, unknown>>,
  productMonth: Array<Record<string, unknown>>,
  productIds: Set<string>,
): Array<Record<string, unknown>> {
  if (selection.selection_type === "item_group") {
    return groupMonth.filter((row) => text(row.item_group_id) === selection.item_group_id);
  }
  return productMonth.filter((row) => productIds.has(text(row.product_id)));
}

function monthlyFromRows(rows: Array<Record<string, unknown>>, includeDistincts: boolean): MonthlyPoint[] {
  const byMonth = new Map<string, MonthlyPoint>();
  for (const row of rows) {
    const month = text(row.month);
    if (!month) continue;
    const current = byMonth.get(month) ?? {
      month, tx_count: null, amount_sum_clean: null, supplier_count: null, receiver_count: null,
      amount_valid_row_count: null, raw_supply_qty_valid_row_count: null,
    };
    current.tx_count = addCount(current.tx_count, asCount(row.tx_count));
    current.amount_sum_clean = addDecimal(current.amount_sum_clean, asDecimal(row.amount_sum_clean));
    current.amount_valid_row_count = addCount(current.amount_valid_row_count, asCount(row.amount_valid_row_count));
    current.raw_supply_qty_valid_row_count = addCount(current.raw_supply_qty_valid_row_count, asCount(row.raw_supply_qty_valid_row_count));
    if (includeDistincts) {
      current.supplier_count = asCount(row.supplier_count_distinct) ?? current.supplier_count;
      current.receiver_count = asCount(row.receiver_count_distinct) ?? current.receiver_count;
    }
    byMonth.set(month, current);
  }
  return [...byMonth.values()].sort((left, right) => left.month.localeCompare(right.month));
}

function rankProducts(
  catalog: Array<Record<string, unknown>>,
  productMonth: Array<Record<string, unknown>>,
): RankedProduct[] {
  return catalog.map((row) => {
    const productId = text(row.product_id);
    const months = productMonth.filter((entry) => text(entry.product_id) === productId);
    return {
      product_id: productId,
      item_name_id: text(row.item_name_id) || productId,
      tx_count: sumCounts(months.map((entry) => asCount(entry.tx_count))) ?? 0,
      amount_sum_clean: sumDecimals(months.map((entry) => asDecimal(entry.amount_sum_clean))),
    };
  }).sort((left, right) => right.tx_count - left.tx_count || left.item_name_id.localeCompare(right.item_name_id, "ko"));
}

function scopedComposition(
  rows: Array<Record<string, unknown>>,
  selection: ApiSelection,
  productIds: Set<string>,
  latestMonth: string | null,
): Array<Record<string, unknown>> {
  if (!latestMonth) return [];
  return rows.filter((row) => {
    if (text(row.month) !== latestMonth) return false;
    if (selection.selection_type === "item_group") {
      return text(row.product_scope) === "item_group" && text(row.product_scope_id) === selection.item_group_id;
    }
    return text(row.product_scope) === "product" && productIds.has(text(row.product_scope_id));
  });
}

function latestComposition(rows: Array<Record<string, unknown>>): CompositionSlice[] {
  return rows.map((row) => ({
    dimension: `${text(row.endpoint)} ${text(row.dimension)}`.trim(),
    dimension_value: text(row.dimension_value) || "미확인",
    entity_count_distinct: asCount(row.entity_count_distinct) ?? 0,
  })).sort((left, right) => right.entity_count_distinct - left.entity_count_distinct).slice(0, TOP_COMPOSITION_LIMIT);
}

function periodChange(series: MonthlyPoint[]): PeriodChange | null {
  if (series.length < 2) return null;
  const first = series[0]!;
  const last = series[series.length - 1]!;
  return {
    start_month: first.month,
    end_month: last.month,
    tx_from: first.tx_count,
    tx_to: last.tx_count,
    supplier_from: first.supplier_count,
    supplier_to: last.supplier_count,
    receiver_from: first.receiver_count,
    receiver_to: last.receiver_count,
  };
}

function receiverMix(
  rows: Array<Record<string, unknown>>,
  denominatorCount: number | null,
  measure: "entity_count_distinct" | "tx_count",
): MixShare[] {
  const buckets = new Map<string, number>();
  for (const row of rows) {
    if (text(row.endpoint) !== "receiver" || text(row.dimension) !== "type") continue;
    const label = bucketReceiverType(text(row.dimension_value));
    buckets.set(label, (buckets.get(label) ?? 0) + (asCount(row[measure]) ?? 0));
  }
  const known = [...buckets.values()].reduce((total, count) => total + count, 0);
  const unknown = denominatorCount == null ? 0 : Math.max(0, denominatorCount - known);
  if (unknown > 0) buckets.set("미확인", unknown);
  const denominator = denominatorCount && denominatorCount > 0 ? denominatorCount : known + unknown;
  if (denominator <= 0) return [];
  const order = ["의료기관", "유통", "제조·수입", "그 외", "미확인"];
  return order.flatMap((label) => {
    const count = buckets.get(label) ?? 0;
    return count > 0 ? [{ label, count, share: count / denominator }] : [];
  });
}

function regionNames(rows: Array<Record<string, unknown>>): string[] {
  return rows.filter((row) => text(row.endpoint) === "receiver" && text(row.dimension) === "region")
    .map((row) => ({ name: text(row.dimension_value) || "미확인", count: asCount(row.entity_count_distinct) ?? 0 }))
    .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name, "ko"))
    .map((item) => item.name);
}

function median(values: Array<number | null>): number | null {
  const present = values.filter((value): value is number => value != null).sort((left, right) => left - right);
  if (!present.length) return null;
  const middle = Math.floor(present.length / 2);
  return present.length % 2 ? present[middle]! : (present[middle - 1]! + present[middle]!) / 2;
}

function ratio(valid: number | null, total: number | null): number | null {
  if (valid == null || total == null || total <= 0) return null;
  return valid / total;
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asCount(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value !== "" && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function asDecimal(value: unknown): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}

function addCount(left: number | null, right: number | null): number | null {
  if (left == null && right == null) return null;
  return (left ?? 0) + (right ?? 0);
}

function sumCounts(values: Array<number | null>): number | null {
  return values.reduce<number | null>((total, value) => addCount(total, value), null);
}

function addDecimal(left: string | null, right: string | null): string | null {
  if (left == null && right == null) return null;
  return fromMicro(toMicro(left ?? "0") + toMicro(right ?? "0"));
}

function sumDecimals(values: Array<string | null>): string | null {
  return values.reduce<string | null>((total, value) => addDecimal(total, value), null);
}

function toMicro(value: string): bigint {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value.trim());
  if (!match) return 0n;
  const sign = match[1] === "-" ? -1n : 1n;
  const fraction = `${match[3] ?? ""}000000`.slice(0, 6);
  return sign * (BigInt(match[2]) * 1_000_000n + BigInt(fraction));
}

function fromMicro(value: bigint): string {
  const sign = value < 0n ? "-" : "";
  const abs = value < 0n ? -value : value;
  const fraction = (abs % 1_000_000n).toString().padStart(6, "0");
  return `${sign}${abs / 1_000_000n}.${fraction}`;
}
