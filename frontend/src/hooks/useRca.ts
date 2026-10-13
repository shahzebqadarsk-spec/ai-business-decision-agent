import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api/rca";
import { useSelectedClient } from "../context/ClientContext";
import type { ComparisonType, Granularity } from "../types/rca";

// useEvidence is generic (backs Forecasting's EvidenceDrawer too); re-exported here so
// existing `import { useEvidence } from "../../hooks/useRca"` call sites keep working.
export { useEvidence } from "./useEvidence";

export function useIssues(
  filters: { periodKey?: string; issueType?: string; status?: string; granularity?: string } = {},
) {
  const { clientId } = useSelectedClient();
  return useQuery({
    queryKey: ["issues", filters, clientId],
    queryFn: () => api.listIssues({ ...filters, clientId }),
  });
}

export function useIssue(issueId: string | undefined) {
  return useQuery({
    queryKey: ["issue", issueId],
    queryFn: () => api.getIssue(issueId as string),
    enabled: issueId !== undefined,
  });
}

export function useIssueEvidence(issueId: string | undefined) {
  return useQuery({
    queryKey: ["issue-evidence", issueId],
    queryFn: () => api.getIssueEvidence(issueId as string),
    enabled: issueId !== undefined,
  });
}

export function useDetectIssues() {
  const queryClient = useQueryClient();
  const { clientId } = useSelectedClient();
  return useMutation({
    mutationFn: ({
      granularity,
      periodKey,
      comparisonType,
    }: {
      granularity: Granularity;
      periodKey: string;
      comparisonType?: ComparisonType;
    }) => api.detectIssues(granularity, periodKey, comparisonType, clientId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });
}

export function useAnalyzeIssue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (issueId: string) => api.analyzeIssue(issueId),
    onSuccess: (issue) => {
      void queryClient.invalidateQueries({ queryKey: ["issues"] });
      void queryClient.invalidateQueries({ queryKey: ["issue", issue.id] });
      void queryClient.invalidateQueries({ queryKey: ["issue-evidence", issue.id] });
    },
  });
}
