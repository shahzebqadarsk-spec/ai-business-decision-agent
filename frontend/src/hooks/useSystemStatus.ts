import { useQuery } from "@tanstack/react-query";
import { fetchLlmStatus, fetchSystemConfig } from "../api/system";

export function useSystemConfig() {
  return useQuery({ queryKey: ["system-config"], queryFn: fetchSystemConfig });
}

export function useLlmStatus() {
  return useQuery({ queryKey: ["llm-status"], queryFn: fetchLlmStatus });
}
