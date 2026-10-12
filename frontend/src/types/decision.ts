/** Phase 7 scope decision (see app/decisions/engine.py): a decision run ranks two or more
 * existing Scenarios against each other on up to three criteria, each itself a deterministic
 * average of that scenario's own ScenarioResult rows -- never a new projection, never an LLM
 * call. Kept in sync with `DECISION_CRITERIA`/`DECISION_STATUSES` on the backend by hand. */
export const DECISION_CRITERIA = ["profitability", "growth", "cost_efficiency"] as const;
export type DecisionCriterion = (typeof DECISION_CRITERIA)[number];

export type DecisionStatus = "completed" | "insufficient_data";

export interface CriteriaBreakdownEntry {
  weight: number;
  value: number | null;
  weighted?: number;
}

export interface DecisionOption {
  id: string;
  decision_run_id: string;
  scenario_id: string | null;
  title: string;
  score: number | null;
  rank: number | null;
  criteria_breakdown: Record<string, CriteriaBreakdownEntry>;
  rationale: string | null;
  evidence_id: string | null;
}

export interface DecisionRun {
  id: string;
  name: string;
  description: string | null;
  criteria_weights: Record<string, number>;
  status: DecisionStatus;
  status_reason: string | null;
  created_at: string;
  options: DecisionOption[];
  fact_evidence_id: string | null;
}
