export const class3AnalysisSchemaVersion = "1.0.0" as const;

export type Class3SelectionType = "item_group" | "item_name";
export type NullableDecimal = string | null;
export type NullableString = string | null;
export type NullableCount = number | null;

export interface Class3SelectionCatalogRow {
  selection_id: string;
  selection_type: Class3SelectionType;
  label: string;
  normalized_label: string;
  source_labels: string[];
  parent_item_group_selection_id: NullableString;
  parent_item_group_label: NullableString;
  parent_conflict_status: "not_applicable" | "none" | "missing" | "multiple";
  quality_flags: string;
}

export interface Class3SelectionMonthMetricRow {
  selection_id: string;
  selection_type: Class3SelectionType;
  month: string;
  tx_count: NullableCount;
  amount_sum_clean: NullableDecimal;
  amount_valid_row_count: NullableCount;
  amount_coverage: NullableDecimal;
  raw_supply_qty_sum: NullableDecimal;
  raw_supply_qty_valid_row_count: NullableCount;
  raw_supply_qty_coverage: NullableDecimal;
  piece_qty_sum: NullableDecimal;
  piece_qty_valid_row_count: NullableCount;
  piece_qty_coverage: NullableDecimal;
  unique_supplier_count: NullableCount;
  unique_receiver_count: NullableCount;
  quality_flags: string;
}

export interface Class3SelectionMonthCompositionRow {
  selection_id: string;
  selection_type: Class3SelectionType;
  month: string;
  dimension: "supplier_type" | "receiver_type" | "supplier_region" | "receiver_region";
  dimension_value: string;
  is_unknown: boolean | null;
  endpoint_count: NullableCount;
  denominator_endpoint_count: NullableCount;
  endpoint_share: NullableDecimal;
  quality_flags: string;
}

export interface Class3SelectionCoverageSummaryRow {
  selection_id: string;
  selection_type: Class3SelectionType;
  period_start: string;
  period_end: string;
  included_months: string[];
  missing_months: string[];
  expected_month_count: NullableCount;
  included_month_count: NullableCount;
  missing_month_count: NullableCount;
  coverage_denominator_tx_count: NullableCount;
  amount_valid_row_count: NullableCount;
  amount_valid_rate: NullableDecimal;
  raw_supply_qty_valid_row_count: NullableCount;
  raw_supply_qty_valid_rate: NullableDecimal;
  piece_qty_valid_row_count: NullableCount;
  piece_qty_valid_rate: NullableDecimal;
  supplier_endpoint_month_count: NullableCount;
  receiver_endpoint_month_count: NullableCount;
  supplier_type_unknown_endpoint_month_count: NullableCount;
  supplier_type_unknown_rate: NullableDecimal;
  receiver_type_unknown_endpoint_month_count: NullableCount;
  receiver_type_unknown_rate: NullableDecimal;
  supplier_region_unknown_endpoint_month_count: NullableCount;
  supplier_region_unknown_rate: NullableDecimal;
  receiver_region_unknown_endpoint_month_count: NullableCount;
  receiver_region_unknown_rate: NullableDecimal;
  source_versions: string[];
  data_version: string;
  fact_schema_version: string;
  analysis_schema_version: string;
  quality_flags: string;
}

export interface Class3AnalysisPayload {
  analysis_schema_version: typeof class3AnalysisSchemaVersion;
  selection_catalog: Class3SelectionCatalogRow[];
  selection_month_metrics: Class3SelectionMonthMetricRow[];
  selection_month_composition: Class3SelectionMonthCompositionRow[];
  selection_coverage_summary: Class3SelectionCoverageSummaryRow[];
}
