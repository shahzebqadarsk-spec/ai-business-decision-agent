import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api/ingestion";
import { useSelectedClient } from "../context/ClientContext";

export function useDatasets() {
  const { clientId } = useSelectedClient();
  return useQuery({ queryKey: ["datasets", clientId], queryFn: () => api.listDatasets(clientId) });
}

export function useDataset(datasetId: string | null) {
  return useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => api.getDataset(datasetId as string),
    enabled: datasetId !== null,
  });
}

export function useCreateDataset() {
  const queryClient = useQueryClient();
  const { clientId } = useSelectedClient();
  return useMutation({
    mutationFn: (name: string) => api.createDataset(name, clientId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}

export function useFiles(datasetId: string | null) {
  return useQuery({
    queryKey: ["files", datasetId],
    queryFn: () => api.listFiles(datasetId as string),
    enabled: datasetId !== null,
  });
}

export function useUploadFile(datasetId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.uploadFile(datasetId as string, file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["files", datasetId] });
      void queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
      void queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}

export function useFileProfile(fileId: string | null) {
  return useQuery({
    queryKey: ["profile", fileId],
    queryFn: () => api.getFileProfile(fileId as string),
    enabled: fileId !== null,
  });
}

export function useQualityIssues(fileId: string | null) {
  return useQuery({
    queryKey: ["quality-issues", fileId],
    queryFn: () => api.getQualityIssues(fileId as string),
    enabled: fileId !== null,
  });
}

export function useMappings(fileId: string | null) {
  return useQuery({
    queryKey: ["mappings", fileId],
    queryFn: () => api.listMappings(fileId as string),
    enabled: fileId !== null,
  });
}

export function useProposeMappings(fileId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.proposeMappings(fileId as string),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mappings", fileId] });
    },
  });
}

export function useConfirmMapping(fileId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ mappingId, field, confirmedBy }: { mappingId: string; field: string; confirmedBy: string }) =>
      api.confirmMapping(fileId as string, mappingId, field, confirmedBy),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mappings", fileId] });
    },
  });
}

export function useRejectMapping(fileId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ mappingId, rejectedBy }: { mappingId: string; rejectedBy: string }) =>
      api.rejectMapping(fileId as string, mappingId, rejectedBy),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mappings", fileId] });
    },
  });
}

export function useMaterialize(fileId: string | null, datasetId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (performedBy: string) => api.materializeFile(fileId as string, performedBy),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
      void queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}

export function useCanonicalFields(table: string) {
  return useQuery({
    queryKey: ["canonical-fields", table],
    queryFn: () => api.listCanonicalFields(table),
    staleTime: Infinity,
  });
}
