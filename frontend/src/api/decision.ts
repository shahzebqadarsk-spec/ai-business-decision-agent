import { apiGet, apiPostJson } from "./client";
import type { DecisionRun } from "../types/decision";

export interface CreateDecisionBody {
  name: string;
  description?: string | null;
  scenario_ids: string[];
  criteria_weights?: Record<string, number> | null;
}

export function compareScenarios(body: CreateDecisionBody): Promise<DecisionRun> {
  return apiPostJson<DecisionRun>("/decisions", body);
}

export function listDecisions(): Promise<DecisionRun[]> {
  return apiGet<DecisionRun[]>("/decisions");
}

export function getDecision(decisionRunId: string): Promise<DecisionRun> {
  return apiGet<DecisionRun>(`/decisions/${decisionRunId}`);
}
