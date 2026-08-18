const MISSING = "검증된 값 없음";

const BC_MODE_LABELS: Record<string, string> = {
  exact: "전체 경로를 계산했습니다",
  deterministic_sample: "경로가 많아 표본으로 계산했습니다",
  deferred_too_large: "관계망이 커서 계산하지 않았습니다",
};

const BC_REASON_LABELS: Record<string, string> = {
  graph_too_large: "관계망이 커서 순위를 매기지 않습니다",
  no_reachable_source_target_pairs: "제조·수입에서 의료기관으로 이어진 경로가 없습니다",
  below_minimum_reachable_pairs: "확인된 경로가 적어 순위를 매기지 않습니다",
  role_group_below_minimum_sample: "같은 역할군 표본이 부족합니다",
};

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function asCount(value: unknown): number | null {
  if (Array.isArray(value)) return value.length;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatCount(value: number | null, suffix = "곳"): string {
  return value == null ? MISSING : `${value}${suffix}`;
}

function formatSigned(value: unknown, suffix = ""): string {
  const parsed = asNumber(value);
  if (parsed == null) return MISSING;
  if (parsed === 0) return "변화 없음";
  const body = Number.isInteger(parsed) ? String(parsed) : String(Number(parsed.toFixed(2)));
  return `${parsed > 0 ? "+" : ""}${body}${suffix}`;
}

function formatPercentile(value: unknown): string | null {
  const parsed = asNumber(value);
  if (parsed == null) return null;
  return String(Number(parsed.toFixed(1)));
}

function formatShare(value: unknown): string {
  const parsed = asNumber(value);
  if (parsed == null) return MISSING;
  return `${Number((parsed * 100).toFixed(1))}%`;
}

function formatMonths(value: unknown): string | null {
  if (!Array.isArray(value) || value.length === 0 || !value.every((item) => typeof item === "string")) {
    return null;
  }
  return value.join(" ~ ");
}

export function presentBcEvidence(raw: unknown): {
  headline: string;
  note: string;
  rows: Array<{ label: string; value: string }>;
} {
  const bc = asRecord(raw);
  const insufficient = bc.insufficient_evidence === true || bc.bc_insufficient_sample === true;
  const percentile = formatPercentile(bc.bc_percentile);
  const reasonKey = typeof bc.bc_rank_reason === "string" ? bc.bc_rank_reason
    : typeof bc.reason === "string" ? bc.reason : "";
  const headline = insufficient
    ? "판단 유보"
    : percentile
      ? `역할군 백분위 ${percentile}`
      : "경로 통과 백분위 없음";
  const rows = [
    { label: "역할군 내 순위", value: asNumber(bc.bc_rank) == null ? MISSING : `${asNumber(bc.bc_rank)}위` },
    { label: "같은 역할군 비교 표본", value: formatCount(asNumber(bc.bc_role_group_sample_size), "곳") },
    { label: "관측 경로에서 차지하는 비중", value: formatShare(bc.gateway_share) },
    { label: "확인된 제조·수입→의료기관 경로 쌍", value: formatCount(asNumber(bc.reachable_source_target_pairs), "쌍") },
    { label: "이 업체를 거쳐 도달한 의료기관", value: formatCount(asNumber(bc.reachable_target_count), "곳") },
    { label: "같은 연결 덩어리 규모", value: formatCount(asNumber(bc.weak_component_size), "곳") },
    {
      label: "계산 범위",
      value: typeof bc.mode === "string" && BC_MODE_LABELS[bc.mode]
        ? BC_MODE_LABELS[bc.mode]
        : MISSING,
    },
  ];
  if (insufficient) {
    rows.unshift({
      label: "유보 사유",
      value: BC_REASON_LABELS[reasonKey] ?? "경로 통과 정도를 순위로 매기지 않습니다",
    });
  }
  return {
    headline,
    note: "GAD-NR과 별도로, 제조·수입에서 의료기관으로 가는 관측 경로가 이 업체를 얼마나 지나가는지 봅니다.",
    rows,
  };
}

export function presentPeriodDiffs(relationshipRaw: unknown, volumeRaw: unknown): {
  headline: string;
  note: string;
  rows: Array<{ label: string; value: string }>;
} {
  const relationship = asRecord(relationshipRaw);
  const volume = asRecord(volumeRaw);
  const added = asCount(relationship.new_counterparty_ids);
  const kept = asCount(relationship.retained_counterparty_ids);
  const lost = asCount(relationship.lost_counterparty_ids);
  const current = formatMonths(relationship.current_months) ?? formatMonths(volume.current_months);
  const previous = formatMonths(relationship.comparison_months);
  const earlier = formatMonths(volume.comparison_months);
  const headline = added == null && lost == null
    ? "거래처 변화를 표시할 수 없습니다"
    : `신규 거래처 ${formatCount(added)} · 소실 ${formatCount(lost)}`;
  const rows = [
    {
      label: previous && current ? `직전 분석 구간(${previous}) 대비 이번 구간(${current}) 신규 거래처` : "직전 분석 구간 대비 신규 거래처",
      value: formatCount(added),
    },
    { label: "유지된 거래처", value: formatCount(kept) },
    { label: "사라진 거래처", value: formatCount(lost) },
    {
      label: earlier && current ? `겹치지 않는 이전 3개월(${earlier}) 대비 거래 건수` : "겹치지 않는 이전 3개월 대비 거래 건수",
      value: formatSigned(volume.tx_count_change, "건"),
    },
    { label: "거래처 수 변화", value: formatSigned(volume.counterparty_count_change, "곳") },
    { label: "품목 수 변화", value: formatSigned(volume.product_count_change, "개") },
    { label: "금액 변화", value: formatSigned(volume.amount_change) },
  ];
  return {
    headline,
    note: "직전 분석 구간과 한 달이 겹치는 비교는 거래처 구성, 겹치지 않는 이전 3개월 비교는 규모만 봅니다.",
    rows,
  };
}
