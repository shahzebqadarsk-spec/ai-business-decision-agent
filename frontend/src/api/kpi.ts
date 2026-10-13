import { apiGet, apiPostJson } from "./client";
import type {
  AvailabilityResult,
  BreakdownResult,
  ComparisonType,
  DashboardPayload,
  Granularity,
  KpiDefinition,
  KpiResult,
} from "../types/kpi";

export function listKpis(): Promise<KpiDefinition[]> {
  return apiGet<KpiDefinition[]>("/kpis");
}

export function getKpi(kpiId: string): Promise<KpiDefinition> {
  return apiGet<KpiDefinition>(`/kpis/${kpiId}`);
}

export function getAvailability(
  kpiId: string,
  granularity: Granularity,
  periodKey: string,
  clientId?: string | null,
): Promise<AvailabilityResult> {
  const params = new URLSearchParams({ granularity, period_key: periodKey });
  if (clientId) params.set("client_id", clientId);
  return apiGet<AvailabilityResult>(`/kpis/${kpiId}/availability?${params.toString()}`);
}

export function calculateKpi(
  kpiId: string,
  granularity: Granularity,
  periodKey: string,
  comparisonType?: ComparisonType,
  clientId?: string | null,
): Promise<KpiResult> {
  return apiPostJson<KpiResult>(`/kpis/${kpiId}/calculate`, {
    granularity,
    period_key: periodKey,
    comparison_type: comparisonType ?? null,
    client_id: clientId ?? null,
  });
}

export function calculateBreakdown(
  kpiId: string,
  granularity: Granularity,
  periodKey: string,
  dimension: string,
  clientId?: string | null,
): Promise<BreakdownResult> {
  return apiPostJson<BreakdownResult>(`/kpis/${kpiId}/breakdown`, {
    granularity,
    period_key: periodKey,
    dimension,
    client_id: clientId ?? null,
  });
}

export function getDashboard(
  periodKey?: string,
  comparisonType: ComparisonType = "YoY",
  clientId?: string | null,
): Promise<DashboardPayload> {
  const params = new URLSearchParams({ comparison_type: comparisonType });
  if (periodKey) params.set("period_key", periodKey);
  if (clientId) params.set("client_id", clientId);
  return apiGet<DashboardPayload>(`/dashboard?${params.toString()}`);
}
