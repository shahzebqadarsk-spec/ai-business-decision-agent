import { useQuery } from "@tanstack/react-query";
import * as evidenceApi from "../api/evidence";

/** Generic Evidence-by-id lookup, shared by RCA and Forecasting (and any later phase that
 * writes Evidence rows) -- the same hook backs `EvidenceDrawer` regardless of which analysis
 * produced the record. */
export function useEvidence(evidenceId: string | undefined) {
  return useQuery({
    queryKey: ["evidence", evidenceId],
    queryFn: () => evidenceApi.getEvidence(evidenceId as string),
    enabled: evidenceId !== undefined,
  });
}
