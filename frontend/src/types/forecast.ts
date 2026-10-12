/** Phase 5 scope decision (see app/forecasting/engine.py): only these three single-summed-
 * column metrics are forecastable, at month granularity only. Kept in sync with
 * `FORECAST_METRICS` on the backend by hand -- the API itself is the source of truth and
 * rejects anything else with a 400. */
export const FORECAST_METRICS = ["revenue", "sales_quantity", "cogs"] as const;
export type ForecastMetric = (typeof FORECAST_METRICS)[number];

export const CONFIDENCE_LEVELS = [0.8, 0.9, 0.95, 0.99] as const;
export type ConfidenceLevel = (typeof CONFIDENCE_LEVELS)[number];

export type ForecastRunStatus = "completed" | "insufficient_data";

export interface ForecastPoint {
  id: string;
  forecast_run_id: string;
  metric: string;
  period_key: string;
  horizon_index: number;
  point_estimate: number;
  lower_bound: number | null;
  upper_bound: number | null;
  evidence_id: string | null;
}

export interface ForecastRun {
  id: string;
  metric: string;
  granularity: string;
  history_start_period: string;
  history_end_period: string;
  history_periods: number;
  horizon_periods: number;
  status: ForecastRunStatus;
  status_reason: string | null;
  method_name: string;
  method_version: string;
  confidence_level: number;
  parameters: Record<string, unknown>;
  holdout_periods: number | null;
  holdout_mae: number | null;
  holdout_mape_pct: number | null;
  created_at: string;
  forecasts: ForecastPoint[];
  fit_evidence_id: string | null;
}
