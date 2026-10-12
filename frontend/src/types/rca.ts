import type { ClaimType, Evidence } from "./evidence";

// Evidence is shared by every analytical phase (RCA, Forecasting, ...) and now lives in its own
// module; re-exported here so existing `import type { Evidence } from "../../types/rca"` call
// sites keep working unchanged.
export type { ClaimType, Evidence };

export type Granularity = "month" | "quarter" | "year";
export type ComparisonType = "YoY" | "QoQ" | "MoM";
export type IssueSeverity = "low" | "medium" | "high" | "critical";
export type IssueStatus = "detected" | "analyzed" | "unavailable";

export interface MaterialityRule {
  threshold: number;
  actual: number;
}

export interface Issue {
  id: string;
  issue_type: string;
  title: string;
  severity: IssueSeverity;
  status: IssueStatus;
  granularity: Granularity;
  period_key: string;
  comparison_period_key: string | null;
  metric: string;
  current_value: number | null;
  prior_value: number | null;
  absolute_change: number | null;
  percentage_change: number | null;
  affected_dimension: string | null;
  affected_entity: string | null;
  materiality: Record<string, MaterialityRule>;
  decomposition: Record<string, unknown> | null;
  detection_run_id: string;
  latest_analysis_run_id: string | null;
  detected_at: string;
  analyzed_at: string | null;
  evidence_ids: string[];
}

export interface AnalysisRun {
  id: string;
  dataset_id: string | null;
  analysis_type: "issue_detection" | "rca";
  granularity: Granularity;
  period_key: string;
  comparison_type: ComparisonType | null;
  comparison_period_key: string | null;
  parameters: Record<string, unknown>;
  status: "pending" | "running" | "completed" | "failed";
  result_summary: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
  issue_ids: string[];
  evidence_ids: string[];
}

/** One row inside a `ContributionBreakdown` payload (app/rca/decomposition.py), as embedded
 * in `Issue.decomposition`. */
export interface ContributionRowPayload {
  dimension_value: string | null;
  current_value: number;
  prior_value: number;
  absolute_contribution: number;
  percentage_contribution: number | null;
  direction: "positive" | "negative" | "flat";
  rank: number | null;
  current_share_pct: number | null;
  is_other_bucket: boolean;
  other_bucket_count: number | null;
  evidence_id: string;
}

export interface ContributionBreakdownPayload {
  total_change: number;
  current_total: number;
  prior_total: number;
  coverage_pct: number | null;
  residual_absolute: number;
  residual_is_material: boolean;
  rows: ContributionRowPayload[];
}

export interface VolumePriceEffectPayload {
  total_change: number;
  volume_effect: number;
  price_effect: number;
  evidence_ids: string[];
}

export interface GrossProfitPayload {
  total_change: number;
  revenue_effect: number;
  cogs_effect: number;
  evidence_ids: string[];
}
