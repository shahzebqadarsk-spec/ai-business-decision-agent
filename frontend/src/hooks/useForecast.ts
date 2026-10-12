import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as forecastApi from "../api/forecast";
import * as kpiApi from "../api/kpi";
import type { ConfidenceLevel, ForecastMetric } from "../types/forecast";

export function useForecastRuns(metric?: string) {
  return useQuery({
    queryKey: ["forecast-runs", metric],
    queryFn: () => forecastApi.listForecastRuns(metric),
  });
}

export function useForecastRun(runId: string | undefined) {
  return useQuery({
    queryKey: ["forecast-run", runId],
    queryFn: () => forecastApi.getForecastRun(runId as string),
    enabled: runId !== undefined,
  });
}

export function useGenerateForecast() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      metric,
      horizonPeriods,
      confidenceLevel,
    }: {
      metric: ForecastMetric;
      horizonPeriods: number;
      confidenceLevel: ConfidenceLevel;
    }) => forecastApi.generateForecast(metric, horizonPeriods, confidenceLevel),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["forecast-runs"] });
    },
  });
}

/** The forecast API only returns the fitted/forecasted points, not the historical actuals it
 * was fit on -- those live in canonical fact_sales and are reached the same way the Executive
 * Dashboard's own revenue trend chart reaches them (Phase 3's generic KPI breakdown endpoint,
 * dimension="month"), one call per calendar year merged chronologically, since a single
 * breakdown call only covers one year at a time. `startYear`/`endYear` normally come straight
 * from a ForecastRun's own history_start_period/history_end_period. */
export function useHistoricalSeries(metric: string | undefined, startYear: number | undefined, endYear: number | undefined) {
  const years = startYear !== undefined && endYear !== undefined
    ? Array.from({ length: endYear - startYear + 1 }, (_, i) => startYear + i)
    : [];

  return useQuery({
    queryKey: ["historical-series", metric, startYear, endYear],
    queryFn: async () => {
      const perYear = await Promise.all(
        years.map((year) => kpiApi.calculateBreakdown(metric as string, "year", String(year), "month")),
      );
      return perYear
        .flatMap((result) => result.rows)
        .filter((row) => row.dimension_value !== null)
        .sort((a, b) => (a.dimension_value as string).localeCompare(b.dimension_value as string));
    },
    enabled: metric !== undefined && years.length > 0,
  });
}
