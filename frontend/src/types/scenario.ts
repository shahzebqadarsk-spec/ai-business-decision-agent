/** Phase 6 scope decision (see app/db/models/scenario.py): a scenario is a plain percentage
 * shock applied to an existing Phase 5 baseline forecast, with gross_profit/gross_margin_pct
 * re-derived from the (possibly adjusted) revenue/cogs using the same formulas Phase 3/4
 * already use. Kept in sync with `SCENARIO_METRICS` on the backend by hand. */
export const SCENARIO_METRICS = ["revenue", "cogs", "gross_profit", "gross_margin_pct"] as const;
export type ScenarioMetric = (typeof SCENARIO_METRICS)[number];

export type ScenarioStatus = "completed" | "insufficient_data";

export interface ScenarioResult {
  id: string;
  scenario_id: string;
  metric: string;
  period_key: string;
  horizon_index: number;
  baseline_value: number | null;
  scenario_value: number;
  delta_absolute: number | null;
  delta_percentage: number | null;
}

export interface Scenario {
  id: string;
  name: string;
  description: string | null;
  revenue_growth_adjustment_pct: number;
  cogs_adjustment_pct: number;
  revenue_forecast_run_id: string | null;
  cogs_forecast_run_id: string | null;
  status: ScenarioStatus;
  status_reason: string | null;
  horizon_periods: number;
  created_at: string;
  results: ScenarioResult[];
}
