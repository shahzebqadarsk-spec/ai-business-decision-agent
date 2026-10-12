import { apiGet } from "./client";
import type { LlmStatus, SystemConfig } from "../types/system";

export function fetchSystemConfig(): Promise<SystemConfig> {
  return apiGet<SystemConfig>("/system/config");
}

export function fetchLlmStatus(): Promise<LlmStatus> {
  return apiGet<LlmStatus>("/llm/status");
}
