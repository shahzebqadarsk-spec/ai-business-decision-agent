import { apiGet, apiPostEmpty, apiPostJson } from "./client";
import type { AnalysisRun, ComparisonType, Evidence, Granularity, Issue } from "../types/rca";

// getEvidence hits the generic /evidence/{id} endpoint also used by Forecasting; re-exported
// here so existing `import { getEvidence } from "../../api/rca"` call sites keep working.
export { getEvidence } from "./evidence";

export function detectIssues(
  granularity: Granularity,
  periodKey: string,
  comparisonType: ComparisonType = "YoY",
): Promise<AnalysisRun> {
  return apiPostJson<AnalysisRun>("/issues/detect", {
    granularity,
    period_key: periodKey,
    comparison_type: comparisonType,
  });
}

export function listIssues(filters: {
  status?: string;
  issueType?: string;
  granularity?: string;
  periodKey?: string;
}): Promise<Issue[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status_filter", filters.status);
  if (filters.issueType) params.set("issue_type", filters.issueType);
  if (filters.granularity) params.set("granularity", filters.granularity);
  if (filters.periodKey) params.set("period_key", filters.periodKey);
  const qs = params.toString();
  return apiGet<Issue[]>(`/issues${qs ? `?${qs}` : ""}`);
}

export function getIssue(issueId: string): Promise<Issue> {
  return apiGet<Issue>(`/issues/${issueId}`);
}

export function analyzeIssue(issueId: string): Promise<Issue> {
  return apiPostEmpty<Issue>(`/issues/${issueId}/analyze`);
}

export function getIssueEvidence(issueId: string): Promise<Evidence[]> {
  return apiGet<Evidence[]>(`/issues/${issueId}/evidence`);
}

export function getAnalysisRun(runId: string): Promise<AnalysisRun> {
  return apiGet<AnalysisRun>(`/analysis-runs/${runId}`);
}
