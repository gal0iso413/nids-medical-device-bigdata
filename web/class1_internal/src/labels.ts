const ROLE_LABELS: Record<string, string> = {
  manufacturer: "제조업체",
  importer: "수입업체",
  distributor: "유통업체",
  hospital: "의료기관",
  other: "기타",
  multi_role: "복합 역할",
  unknown: "역할 미정",
};

export function roleLabel(roleGroup: string) {
  return ROLE_LABELS[roleGroup] ?? roleGroup;
}
