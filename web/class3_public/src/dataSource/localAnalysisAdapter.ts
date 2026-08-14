import {
  class3AnalysisSchemaVersion,
  type Class3AnalysisPayload,
  type Class3SelectionCatalogRow,
  type Class3SelectionCoverageSummaryRow,
  type Class3SelectionMonthCompositionRow,
  type Class3SelectionMonthMetricRow,
} from "../contracts/class3Analysis";

type RecordValue = Record<string, unknown>;

function record(value: unknown, label: string): RecordValue {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object.`);
  }
  return value as RecordValue;
}

function array(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array.`);
  return value;
}

function string(value: unknown, label: string, nullable = false): string | null {
  if (nullable && value === null) return null;
  if (typeof value !== "string") throw new Error(`${label} must be a string${nullable ? " or null" : ""}.`);
  return value;
}

function count(value: unknown, label: string): number | null {
  if (value === null) return null;
  if (typeof value !== "number" || !Number.isInteger(value)) throw new Error(`${label} must be an integer or null.`);
  return value;
}

function decimal(value: unknown, label: string): string | null {
  return string(value, label, true);
}

function strings(value: unknown, label: string): string[] {
  return array(value, label).map((item, index) => string(item, `${label}[${index}]`)!);
}

function catalogRow(value: unknown, index: number): Class3SelectionCatalogRow {
  const row = record(value, `selection_catalog[${index}]`);
  const type = string(row.selection_type, "selection_type");
  if (type !== "item_group" && type !== "item_name") throw new Error("selection_type is invalid.");
  const parentStatus = string(row.parent_conflict_status, "parent_conflict_status");
  if (!(["not_applicable", "none", "missing", "multiple"] as const).includes(parentStatus as never)) throw new Error("parent_conflict_status is invalid.");
  return { selection_id: string(row.selection_id, "selection_id")!, selection_type: type, label: string(row.label, "label")!, normalized_label: string(row.normalized_label, "normalized_label")!, source_labels: strings(row.source_labels, "source_labels"), parent_item_group_selection_id: string(row.parent_item_group_selection_id, "parent_item_group_selection_id", true), parent_item_group_label: string(row.parent_item_group_label, "parent_item_group_label", true), parent_conflict_status: parentStatus as Class3SelectionCatalogRow["parent_conflict_status"], quality_flags: string(row.quality_flags, "quality_flags")! };
}

function metricsRow(value: unknown, index: number): Class3SelectionMonthMetricRow {
  const row = record(value, `selection_month_metrics[${index}]`);
  const type = string(row.selection_type, "selection_type");
  if (type !== "item_group" && type !== "item_name") throw new Error("selection_type is invalid.");
  return { selection_id: string(row.selection_id, "selection_id")!, selection_type: type, month: string(row.month, "month")!, tx_count: count(row.tx_count, "tx_count"), amount_sum_clean: decimal(row.amount_sum_clean, "amount_sum_clean"), amount_valid_row_count: count(row.amount_valid_row_count, "amount_valid_row_count"), amount_coverage: decimal(row.amount_coverage, "amount_coverage"), raw_supply_qty_sum: decimal(row.raw_supply_qty_sum, "raw_supply_qty_sum"), raw_supply_qty_valid_row_count: count(row.raw_supply_qty_valid_row_count, "raw_supply_qty_valid_row_count"), raw_supply_qty_coverage: decimal(row.raw_supply_qty_coverage, "raw_supply_qty_coverage"), piece_qty_sum: decimal(row.piece_qty_sum, "piece_qty_sum"), piece_qty_valid_row_count: count(row.piece_qty_valid_row_count, "piece_qty_valid_row_count"), piece_qty_coverage: decimal(row.piece_qty_coverage, "piece_qty_coverage"), unique_supplier_count: count(row.unique_supplier_count, "unique_supplier_count"), unique_receiver_count: count(row.unique_receiver_count, "unique_receiver_count"), quality_flags: string(row.quality_flags, "quality_flags")! };
}

function compositionRow(value: unknown, index: number): Class3SelectionMonthCompositionRow {
  const row = record(value, `selection_month_composition[${index}]`);
  const type = string(row.selection_type, "selection_type");
  const dimension = string(row.dimension, "dimension");
  if ((type !== "item_group" && type !== "item_name") || !(["supplier_type", "receiver_type", "supplier_region", "receiver_region"] as const).includes(dimension as never)) throw new Error("composition enum is invalid.");
  if (row.is_unknown !== null && typeof row.is_unknown !== "boolean") throw new Error("is_unknown must be boolean or null.");
  return { selection_id: string(row.selection_id, "selection_id")!, selection_type: type, month: string(row.month, "month")!, dimension: dimension as Class3SelectionMonthCompositionRow["dimension"], dimension_value: string(row.dimension_value, "dimension_value")!, is_unknown: row.is_unknown as boolean | null, endpoint_count: count(row.endpoint_count, "endpoint_count"), denominator_endpoint_count: count(row.denominator_endpoint_count, "denominator_endpoint_count"), endpoint_share: decimal(row.endpoint_share, "endpoint_share"), quality_flags: string(row.quality_flags, "quality_flags")! };
}

function coverageRow(value: unknown, index: number): Class3SelectionCoverageSummaryRow {
  const row = record(value, `selection_coverage_summary[${index}]`);
  const type = string(row.selection_type, "selection_type");
  if (type !== "item_group" && type !== "item_name") throw new Error("selection_type is invalid.");
  const fields = ["expected_month_count", "included_month_count", "missing_month_count", "coverage_denominator_tx_count", "amount_valid_row_count", "raw_supply_qty_valid_row_count", "piece_qty_valid_row_count", "supplier_endpoint_month_count", "receiver_endpoint_month_count", "supplier_type_unknown_endpoint_month_count", "receiver_type_unknown_endpoint_month_count", "supplier_region_unknown_endpoint_month_count", "receiver_region_unknown_endpoint_month_count"] as const;
  const rates = ["amount_valid_rate", "raw_supply_qty_valid_rate", "piece_qty_valid_rate", "supplier_type_unknown_rate", "receiver_type_unknown_rate", "supplier_region_unknown_rate", "receiver_region_unknown_rate"] as const;
  const checked = Object.fromEntries(fields.map((field) => [field, count(row[field], field)])) as Record<(typeof fields)[number], number | null>;
  const checkedRates = Object.fromEntries(rates.map((field) => [field, decimal(row[field], field)])) as Record<(typeof rates)[number], string | null>;
  return { selection_id: string(row.selection_id, "selection_id")!, selection_type: type, period_start: string(row.period_start, "period_start")!, period_end: string(row.period_end, "period_end")!, included_months: strings(row.included_months, "included_months"), missing_months: strings(row.missing_months, "missing_months"), ...checked, ...checkedRates, source_versions: strings(row.source_versions, "source_versions"), data_version: string(row.data_version, "data_version")!, fact_schema_version: string(row.fact_schema_version, "fact_schema_version")!, analysis_schema_version: string(row.analysis_schema_version, "analysis_schema_version")!, quality_flags: string(row.quality_flags, "quality_flags")! };
}

export function validateClass3AnalysisPayload(value: unknown): Class3AnalysisPayload {
  const payload = record(value, "payload");
  if (payload.analysis_schema_version !== class3AnalysisSchemaVersion) throw new Error(`Unsupported analysis_schema_version: ${String(payload.analysis_schema_version)}.`);
  return { analysis_schema_version: class3AnalysisSchemaVersion, selection_catalog: array(payload.selection_catalog, "selection_catalog").map(catalogRow), selection_month_metrics: array(payload.selection_month_metrics, "selection_month_metrics").map(metricsRow), selection_month_composition: array(payload.selection_month_composition, "selection_month_composition").map(compositionRow), selection_coverage_summary: array(payload.selection_coverage_summary, "selection_coverage_summary").map(coverageRow) };
}

export async function loadLocalClass3Analysis(url: string, request = fetch): Promise<Class3AnalysisPayload> {
  const response = await request(url);
  if (!response.ok) throw new Error(`Local analysis request failed (${response.status}).`);
  return validateClass3AnalysisPayload(await response.json());
}
