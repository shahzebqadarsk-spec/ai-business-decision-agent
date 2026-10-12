import { apiGet, apiPostJson } from "./client";
import type { Scenario } from "../types/scenario";

export interface CreateScenarioBody {
  name: string;
  description?: string | null;
  revenue_growth_adjustment_pct?: number;
  cogs_adjustment_pct?: number;
  revenue_forecast_run_id?: string | null;
  cogs_forecast_run_id?: string | null;
}

export function generateScenario(body: CreateScenarioBody): Promise<Scenario> {
  return apiPostJson<Scenario>("/scenarios", body);
}

export function listScenarios(): Promise<Scenario[]> {
  return apiGet<Scenario[]>("/scenarios");
}

export function getScenario(scenarioId: string): Promise<Scenario> {
  return apiGet<Scenario>(`/scenarios/${scenarioId}`);
}
