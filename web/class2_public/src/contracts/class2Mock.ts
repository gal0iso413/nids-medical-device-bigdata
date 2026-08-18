export const releaseStatuses = [
  "released",
  "suppressed_small_cell",
  "suppressed_dominance",
  "suppressed_differencing",
  "insufficient_coverage",
  "not_available",
] as const;

export type ReleaseStatus = (typeof releaseStatuses)[number];
export const viewStates = ["results", "empty"] as const;
export type ViewState = (typeof viewStates)[number];
export type SelectionType = "item_group" | "item_name";

export interface SelectionItem {
  type: SelectionType;
  id: string;
  label: string;
}
export interface PerItemResult {
  selection_id: string;
  selection_type: SelectionType;
  release_status: ReleaseStatus;
  notice: string;
  released_content?: {
    activity_label: string;
    quantity_label: string;
    trend_label: string;
  };
}

export interface PortfolioSummary {
  release_status: ReleaseStatus;
  notice: string;
  released_composition?: {
    entries: Array<{
      selection_id: string;
      share_label: string;
    }>;
    non_additive_notice: string;
  };
}

export interface ObservedReach {
  release_status: ReleaseStatus;
  notice: string;
  released_stages?: Array<{
    stage_label: string;
    display_label: string;
  }>;
}

export interface Class2MockFixture {
  schema_version: "class2-mock-view-v1";
  data_version: string;
  policy_version: "development-unapproved";
  synthetic: true;
  development_notice: string;
  view_state: ViewState;
  release_status: ReleaseStatus;
  selection_summary: {
    selections: SelectionItem[];
    period: {
      start_month: string;
      end_month: string;
    };
  };
  per_item_results: PerItemResult[];
  portfolio_summary: PortfolioSummary;
  observed_reach: ObservedReach;
  coverage: {
    release_status: ReleaseStatus;
    field_states: Array<{
      field: string;
      state: "available" | "suppressed" | "missing" | "not_available";
      notice: string;
    }>;
  };
}
