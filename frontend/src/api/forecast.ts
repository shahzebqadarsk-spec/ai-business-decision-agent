import { apiGet, apiPostJson } from "./client";
import type { ForecastRun } from "../types/forecast";

export function generateForecast(
  metric: string,
  horizonPeriods: number,
  confidenceLevel: number = 0.8,
): Promise<ForecastRun> {
  return apiPostJson<ForecastRun>("/forecasts/generate", {
    metric,
    horizon_periods: horizonPeriods,
    confidence_level: confidenceLevel,
  });
}

export function listForecastRuns(metric?: string): Promise<ForecastRun[]> {
  const qs = metric ? `?metric=${encodeURIComponent(metric)}` : "";
  return apiGet<ForecastRun[]>(`/forecasts/runs${qs}`);
}

export function getForecastRun(runId: string): Promise<ForecastRun> {
  return apiGet<ForecastRun>(`/forecasts/runs/${runId}`);
}
