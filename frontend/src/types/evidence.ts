/** The Evidence model (app/db/models/analysis.py) is shared by every analytical phase --
 * Phase 4 (RCA: fact/contribution claims), Phase 5 (Forecasting: fact/inference claims), and
 * Phase 7 (Decision Scoring: fact/recommendation claims) all write rows here and all link to
 * it the same way (an `evidence_id` pointing at `/evidence/{id}`). This type lives in its own
 * module, rather than under `types/rca.ts`, because it is not RCA-specific; `types/rca.ts`
 * re-exports it for backward compatibility with existing imports. */

export type ClaimType = "fact" | "contribution" | "inference" | "recommendation";

export interface Evidence {
  id: string;
  analysis_run_id: string | null;
  issue_id: string | null;
  forecast_run_id: string | null;
  forecast_id: string | null;
  decision_run_id: string | null;
  decision_option_id: string | null;
  claim_type: ClaimType;
  claim: string;
  metric: string | null;
  unit: string | null;
  granularity: string | null;
  period_key: string | null;
  comparison_period_key: string | null;
  dimension: string | null;
  dimension_value: string | null;
  value: number | null;
  comparison_value: number | null;
  absolute_change: number | null;
  percentage_change: number | null;
  contribution_to_total_pct: number | null;
  source_dataset_id: string | null;
  source_file_ids: string[];
  source_fields: string[];
  calculation_name: string;
  calculation_version: string;
  calculation_parameters: Record<string, unknown>;
  quality_metadata: Record<string, unknown>;
  data: Record<string, unknown>;
  created_at: string;
}
