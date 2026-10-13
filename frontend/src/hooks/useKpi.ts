import { useQuery } from "@tanstack/react-query";
import * as api from "../api/kpi";
import { useSelectedClient } from "../context/ClientContext";
import type { ComparisonType, Granularity } from "../types/kpi";

export function useKpiCatalog() {
  return useQuery({ queryKey: ["kpi-catalog"], queryFn: api.listKpis, staleTime: Infinity });
}

export function useDashboard(periodKey: string | undefined, comparisonType: ComparisonType = "YoY") {
  const { clientId } = useSelectedClient();
  return useQuery({
    queryKey: ["dashboard", periodKey, comparisonType, clientId],
    queryFn: () => api.getDashboard(periodKey, comparisonType, clientId),
  });
}

export function useKpiCalculate(
  kpiId: string,
  granularity: Granularity,
  periodKey: string,
  comparisonType?: ComparisonType,
) {
  const { clientId } = useSelectedClient();
  return useQuery({
    queryKey: ["kpi-calculate", kpiId, granularity, periodKey, comparisonType, clientId],
    queryFn: () => api.calculateKpi(kpiId, granularity, periodKey, comparisonType, clientId),
  });
}

export function useKpiBreakdown(kpiId: string, granularity: Granularity, periodKey: string, dimension: string) {
  const { clientId } = useSelectedClient();
  return useQuery({
    queryKey: ["kpi-breakdown", kpiId, granularity, periodKey, dimension, clientId],
    queryFn: () => api.calculateBreakdown(kpiId, granularity, periodKey, dimension, clientId),
  });
}
