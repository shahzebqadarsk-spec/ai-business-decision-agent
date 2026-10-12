import { apiGet } from "./client";
import type { Evidence } from "../types/evidence";

/** `/evidence/{id}` is a single generic endpoint shared by every phase that writes Evidence
 * rows (RCA's issue/contribution evidence, Forecasting's fact/inference evidence, ...). */
export function getEvidence(evidenceId: string): Promise<Evidence> {
  return apiGet<Evidence>(`/evidence/${evidenceId}`);
}
