import type { Class2AnalysisPayload } from "../contracts/class2Analysis";

export const syntheticClass2AnalysisPayload: Class2AnalysisPayload = {
  analysis_schema_version: "1.0.0",
  selection_catalog: [
    { selection_id: "test:group", selection_type: "item_group", label: "TEST_GROUP", normalized_label: "test_group", source_labels: ["TEST_GROUP"], parent_item_group_selection_id: null, parent_item_group_label: null, parent_conflict_status: "not_applicable", quality_flags: "" },
    { selection_id: "test:name:group-a", selection_type: "item_name", label: "TEST_NAME", normalized_label: "test_name", source_labels: ["TEST_NAME"], parent_item_group_selection_id: "test:group", parent_item_group_label: "TEST_GROUP", parent_conflict_status: "none", quality_flags: "" },
    { selection_id: "test:name:group-b", selection_type: "item_name", label: "TEST_NAME", normalized_label: "test_name", source_labels: ["TEST_NAME"], parent_item_group_selection_id: "test:other-group", parent_item_group_label: "TEST_OTHER_GROUP", parent_conflict_status: "multiple", quality_flags: "" },
  ],
  selection_month_metrics: [
    { selection_id: "test:group", selection_type: "item_group", month: "202401", tx_count: 2, amount_sum_clean: "123456789.123456", amount_valid_row_count: 2, amount_coverage: "1.000000", raw_supply_qty_sum: "7.000000", raw_supply_qty_valid_row_count: 2, raw_supply_qty_coverage: "1.000000", piece_qty_sum: null, piece_qty_valid_row_count: 0, piece_qty_coverage: "0.000000", unique_supplier_count: 2, unique_receiver_count: 1, quality_flags: "test_metric_flag" },
    { selection_id: "test:name:group-a", selection_type: "item_name", month: "202402", tx_count: 1, amount_sum_clean: "0.000001", amount_valid_row_count: 1, amount_coverage: "1.000000", raw_supply_qty_sum: "3.000000", raw_supply_qty_valid_row_count: 1, raw_supply_qty_coverage: "1.000000", piece_qty_sum: "30.000000", piece_qty_valid_row_count: 1, piece_qty_coverage: "1.000000", unique_supplier_count: 1, unique_receiver_count: 1, quality_flags: "" },
  ],
  selection_month_composition: [
    { selection_id: "test:group", selection_type: "item_group", month: "202401", dimension: "supplier_type", dimension_value: "unknown", is_unknown: true, endpoint_count: 2, denominator_endpoint_count: 2, endpoint_share: "1.000000", quality_flags: "supplier_type_conflict" },
  ],
  selection_coverage_summary: [
    { selection_id: "test:group", selection_type: "item_group", period_start: "202401", period_end: "202402", included_months: ["202401"], missing_months: ["202402"], expected_month_count: 2, included_month_count: 1, missing_month_count: 1, coverage_denominator_tx_count: 2, amount_valid_row_count: 2, amount_valid_rate: "1.000000", raw_supply_qty_valid_row_count: 2, raw_supply_qty_valid_rate: "1.000000", piece_qty_valid_row_count: 0, piece_qty_valid_rate: "0.000000", supplier_endpoint_month_count: 2, receiver_endpoint_month_count: 1, supplier_type_unknown_endpoint_month_count: 2, supplier_type_unknown_rate: "1.000000", receiver_type_unknown_endpoint_month_count: 0, receiver_type_unknown_rate: "0.000000", supplier_region_unknown_endpoint_month_count: 0, supplier_region_unknown_rate: "0.000000", receiver_region_unknown_endpoint_month_count: 0, receiver_region_unknown_rate: "0.000000", source_versions: ["test-source"], data_version: "test-manifest", fact_schema_version: "1.0.0", analysis_schema_version: "1.0.0", quality_flags: "test_coverage_flag" },
  ],
};
