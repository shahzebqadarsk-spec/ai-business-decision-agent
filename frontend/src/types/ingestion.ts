export type DatasetStatus = "uploaded" | "profiled" | "mapping" | "materialized" | "failed";

export interface Dataset {
  id: string;
  name: string;
  status: DatasetStatus;
  created_at: string;
}

export type FileStatus = "validated" | "rejected";

export interface DatasetFile {
  id: string;
  dataset_id: string;
  original_filename: string;
  status: FileStatus;
  size_bytes: number;
  row_count: number | null;
  rejection_reason: string | null;
  created_at: string;
}

export interface ColumnProfile {
  column_name: string;
  position: number;
  inferred_dtype: string;
  classification: string | null;
  null_count: number;
  null_percentage: number;
  unique_count: number;
  sample_values: unknown[];
  min_value: string | null;
  max_value: string | null;
  mean_value: number | null;
  stddev_value: number | null;
  date_min: string | null;
  date_max: string | null;
}

export type QualitySeverity = "info" | "warning" | "error";

export interface QualityIssue {
  id: string;
  column_name: string | null;
  issue_type: string;
  severity: QualitySeverity;
  description: string;
  affected_row_count: number | null;
}

export type MappingStatus = "proposed" | "confirmed" | "rejected" | "unresolved";
export type MappingMethod = "rule" | "llm";

export interface ColumnMapping {
  id: string;
  source_column: string;
  proposed_canonical_field: string | null;
  confidence: number;
  method: MappingMethod;
  reason: string | null;
  status: MappingStatus;
  confirmed_canonical_field: string | null;
  confirmed_by: string | null;
}

export interface CanonicalField {
  name: string;
  required: boolean;
  data_type: string;
}

export interface MaterializeResult {
  rows_written: number;
  rows_skipped: number;
  skipped_reasons: string[];
}
