import { apiGet, apiPostEmpty, apiPostForm, apiPostJson } from "./client";
import type {
  CanonicalField,
  ColumnMapping,
  ColumnProfile,
  Dataset,
  DatasetFile,
  MaterializeResult,
  QualityIssue,
} from "../types/ingestion";

export function createDataset(name: string, clientId?: string | null): Promise<Dataset> {
  return apiPostJson<Dataset>("/datasets", { name, client_id: clientId ?? null });
}

export function listDatasets(clientId?: string | null): Promise<Dataset[]> {
  const params = new URLSearchParams();
  if (clientId) params.set("client_id", clientId);
  const qs = params.toString();
  return apiGet<Dataset[]>(`/datasets${qs ? `?${qs}` : ""}`);
}

export function getDataset(datasetId: string): Promise<Dataset> {
  return apiGet<Dataset>(`/datasets/${datasetId}`);
}

export function listFiles(datasetId: string): Promise<DatasetFile[]> {
  return apiGet<DatasetFile[]>(`/datasets/${datasetId}/files`);
}

export function uploadFile(datasetId: string, file: File): Promise<DatasetFile> {
  const form = new FormData();
  form.append("file", file);
  return apiPostForm<DatasetFile>(`/datasets/${datasetId}/files`, form);
}

export function getFileProfile(fileId: string): Promise<ColumnProfile[]> {
  return apiGet<ColumnProfile[]>(`/datasets/files/${fileId}/profile`);
}

export function getQualityIssues(fileId: string): Promise<QualityIssue[]> {
  return apiGet<QualityIssue[]>(`/datasets/files/${fileId}/quality-issues`);
}

export function proposeMappings(fileId: string): Promise<ColumnMapping[]> {
  return apiPostEmpty<ColumnMapping[]>(`/datasets/files/${fileId}/mappings/propose`);
}

export function listMappings(fileId: string): Promise<ColumnMapping[]> {
  return apiGet<ColumnMapping[]>(`/datasets/files/${fileId}/mappings`);
}

export function confirmMapping(
  fileId: string,
  mappingId: string,
  confirmedCanonicalField: string,
  confirmedBy: string,
): Promise<ColumnMapping> {
  return apiPostJson<ColumnMapping>(`/datasets/files/${fileId}/mappings/${mappingId}/confirm`, {
    confirmed_canonical_field: confirmedCanonicalField,
    confirmed_by: confirmedBy,
  });
}

export function rejectMapping(
  fileId: string,
  mappingId: string,
  rejectedBy: string,
): Promise<ColumnMapping> {
  return apiPostJson<ColumnMapping>(`/datasets/files/${fileId}/mappings/${mappingId}/reject`, {
    rejected_by: rejectedBy,
  });
}

export function materializeFile(fileId: string, performedBy: string): Promise<MaterializeResult> {
  return apiPostJson<MaterializeResult>(`/datasets/files/${fileId}/materialize`, {
    performed_by: performedBy,
  });
}

export function listCanonicalFields(table: string): Promise<CanonicalField[]> {
  return apiGet<CanonicalField[]>(`/canonical-fields/${table}`);
}
