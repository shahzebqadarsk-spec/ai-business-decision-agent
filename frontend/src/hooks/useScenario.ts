import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as scenarioApi from "../api/scenario";
import type { CreateScenarioBody } from "../api/scenario";
import { useSelectedClient } from "../context/ClientContext";

export function useScenarios() {
  const { clientId } = useSelectedClient();
  return useQuery({
    queryKey: ["scenarios", clientId],
    queryFn: () => scenarioApi.listScenarios(clientId),
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
  const { clientId } = useSelectedClient();
  return useMutation({
    mutationFn: (body: CreateScenarioBody) => scenarioApi.generateScenario({ ...body, client_id: clientId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["scenarios"] });
    },
  });
}
