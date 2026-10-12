import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as decisionApi from "../api/decision";
import type { CreateDecisionBody } from "../api/decision";

export function useDecisions() {
  return useQuery({
    queryKey: ["decisions"],
    queryFn: () => decisionApi.listDecisions(),
  });
}

export function useDecision(decisionRunId: string | undefined) {
  return useQuery({
    queryKey: ["decision", decisionRunId],
    queryFn: () => decisionApi.getDecision(decisionRunId as string),
    enabled: decisionRunId !== undefined,
  });
}

export function useCompareScenarios() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateDecisionBody) => decisionApi.compareScenarios(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["decisions"] });
    },
  });
}
