import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as scenarioApi from "../api/scenario";
import type { CreateScenarioBody } from "../api/scenario";

export function useScenarios() {
  return useQuery({
    queryKey: ["scenarios"],
    queryFn: () => scenarioApi.listScenarios(),
  });
}

export function useScenario(scenarioId: string | undefined) {
  return useQuery({
    queryKey: ["scenario", scenarioId],
    queryFn: () => scenarioApi.getScenario(scenarioId as string),
    enabled: scenarioId !== undefined,
  });
}

export function useGenerateScenario() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateScenarioBody) => scenarioApi.generateScenario(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["scenarios"] });
    },
  });
}
