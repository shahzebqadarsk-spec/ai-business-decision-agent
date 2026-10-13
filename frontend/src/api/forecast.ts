import { apiGet, apiPostJson } from "./client";
import type { ForecastRun } from "../types/forecast";

export function generateForecast(
  metric: string,
  horizonPeriods: number,
  confidenceLevel: number = 0.8,
  clientId?: string | null,
): Promise<ForecastRun> {
  return apiPostJson<ForecastRun>("/forecasts/generate", {
    metric,
    horizon_periods: horizonPeriods,
    confidence_level: confidenceLevel,
    client_id: clientId ?? null,
  });
}

export function listForecastRuns(metric?: string, clientId?: string | null): Promise<ForecastRun[]> {
  const params = new URLSearchParams();
  if (metric) params.set("metric", metric);
  if (clientId) params.set("client_id", clientId);
  const qs = params.toString();
  return apiGet<ForecastRun[]>(`/forecasts/runs${qs ? `?${qs}` : ""}`);
}

export function getForecastRun(runId: string): Promise<ForecastRun> {
  return apiGet<ForecastRun>(`/forecasts/runs/${runId}`);
}
