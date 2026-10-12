import { useQuery } from "@tanstack/react-query";
import * as api from "../api/kpi";
import type { ComparisonType, Granularity } from "../types/kpi";

export function useKpiCatalog() {
  return useQuery({ queryKey: ["kpi-catalog"], queryFn: api.listKpis, staleTime: Infinity });
}

export function useDashboard(periodKey: string | undefined, comparisonType: ComparisonType = "YoY") {
  return useQuery({
    queryKey: ["dashboard", periodKey, comparisonType],
    queryFn: () => api.getDashboard(periodKey, comparisonType),
  });
}

export function useKpiCalculate(
  kpiId: string,
  granularity: Granularity,
  periodKey: string,
  comparisonType?: ComparisonType,
) {
  return useQuery({
    queryKey: ["kpi-calculate", kpiId, granularity, periodKey, comparisonType],
    queryFn: () => api.calculateKpi(kpiId, granularity, periodKey, comparisonType),
  });
}

export function useKpiBreakdown(kpiId: string, granularity: Granularity, periodKey: string, dimension: string) {
  return useQuery({
    queryKey: ["kpi-breakdown", kpiId, granularity, periodKey, dimension],
    queryFn: () => api.calculateBreakdown(kpiId, granularity, periodKey, dimension),
  });
}
