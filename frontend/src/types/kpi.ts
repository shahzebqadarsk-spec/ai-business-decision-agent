export type KpiCategory = "financial" | "sales" | "cost" | "operations";
export type KpiUnit = "currency" | "count" | "quantity" | "percentage" | "ratio" | "days" | "hours";
export type KpiStatus = "available" | "cannot_compute" | "insufficient_data" | "invalid_data";
export type Granularity = "month" | "quarter" | "year";
export type ComparisonType = "YoY" | "QoQ" | "MoM";

export interface KpiDefinition {
  kpi_id: string;
  name: string;
  description: string;
  category: KpiCategory;
  unit: KpiUnit;
  currency: string | null;
  required_canonical_tables: string[];
  required_fields: string[];
  aggregation_method: string;
  supported_dimensions: string[];
  supported_granularities: string[];
  comparison_types: string[];
  implemented: boolean;
}

export interface KpiResult {
  kpi_id: string;
  name: string;
  unit: KpiUnit;
  currency: string | null;
  granularity: Granularity;
  period_key: string;
  status: KpiStatus;
  status_reason: string | null;
  value: number | null;
  comparison_type: ComparisonType | null;
  comparison_period_key: string | null;
  comparison_value: number | null;
  absolute_change: number | null;
  percentage_change: number | null;
  percentage_change_status: string;
  data_coverage: Record<string, unknown>;
  source_file_ids: string[];
  source_fields: string[];
  calculation_version: string;
  calculated_at: string;
}

export interface AvailabilityResult {
  kpi_id: string;
  granularity: Granularity;
  period_key: string;
  status: KpiStatus;
  status_reason: string | null;
}

export interface DimensionBreakdownRow {
  dimension_value: string | null;
  value: number | null;
  status: KpiStatus;
  rank: number | null;
  share_pct: number | null;
}

export interface BreakdownResult {
  kpi_id: string;
  name: string;
  unit: KpiUnit;
  currency: string | null;
  granularity: Granularity;
  period_key: string;
  dimension: string;
  rows: DimensionBreakdownRow[];
}

export interface DashboardPayload {
  granularity: Granularity;
  period_key: string;
  comparison_type: ComparisonType;
  cards: KpiResult[];
  revenue_trend: DimensionBreakdownRow[];
  revenue_by_region: DimensionBreakdownRow[];
  revenue_by_product: DimensionBreakdownRow[];
  top_customers: DimensionBreakdownRow[];
  bottom_customers: DimensionBreakdownRow[];
}
