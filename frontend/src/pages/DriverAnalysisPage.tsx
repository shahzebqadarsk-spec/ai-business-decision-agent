import { useState } from "react";
import { Card } from "../components/ui/card";
import { IssueList } from "../components/rca/IssueList";
import { IssueDetail } from "../components/rca/IssueDetail";
import { EvidenceDrawer } from "../components/evidence/EvidenceDrawer";
import { useDetectIssues, useIssue, useIssues } from "../hooks/useRca";
import type { ComparisonType, Granularity } from "../types/rca";

const GRANULARITIES: Granularity[] = ["year", "quarter", "month"];
const COMPARISON_TYPES: ComparisonType[] = ["YoY", "QoQ", "MoM"];

export function DriverAnalysisPage() {
  const [granularity, setGranularity] = useState<Granularity>("year");
  const [periodKey, setPeriodKey] = useState("2025");
  const [comparisonType, setComparisonType] = useState<ComparisonType>("YoY");
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);

  const issuesQuery = useIssues({ periodKey, granularity });
  const issueQuery = useIssue(selectedIssueId ?? undefined);
  const detectMutation = useDetectIssues();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Issues &amp; Driver Analysis</h2>
      </div>
      <p className="text-xs text-slate-400">
        Deterministic problem detection and root-cause / driver analysis. Figures here describe
        statistical contribution and association, never proven causation (see the caveat on each
        breakdown).
      </p>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col text-xs text-slate-500">
            Granularity
            <select
              value={granularity}
              onChange={(e) => setGranularity(e.target.value as Granularity)}
              className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
            >
              {GRANULARITIES.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-xs text-slate-500">
            Period
            <input
              type="text"
              value={periodKey}
              onChange={(e) => setPeriodKey(e.target.value)}
              className="mt-1 w-28 rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
          <label className="flex flex-col text-xs text-slate-500">
            Comparison
            <select
              value={comparisonType}
              onChange={(e) => setComparisonType(e.target.value as ComparisonType)}
              className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
            >
              {COMPARISON_TYPES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => detectMutation.mutate({ granularity, periodKey, comparisonType })}
            disabled={detectMutation.isPending}
            className="rounded bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
          >
            {detectMutation.isPending ? "Detecting..." : "Detect issues"}
          </button>
        </div>
        {detectMutation.isError && (
          <p className="mt-2 text-xs text-red-600">Could not run issue detection for this period.</p>
        )}
      </Card>

      {issuesQuery.isLoading && (
        <Card>
          <p className="text-sm text-slate-500">Loading issues...</p>
        </Card>
      )}
      {issuesQuery.isError && (
        <Card>
          <p className="text-sm text-red-600">Could not reach the backend.</p>
        </Card>
      )}

      {issuesQuery.data && (
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <IssueList
            issues={issuesQuery.data}
            selectedId={selectedIssueId}
            onSelect={setSelectedIssueId}
          />
          <div>
            {!selectedIssueId && (
              <Card>
                <p className="text-sm text-slate-400">Select an issue to see its driver analysis.</p>
              </Card>
            )}
            {selectedIssueId && issueQuery.isLoading && (
              <Card>
                <p className="text-sm text-slate-500">Loading issue...</p>
              </Card>
            )}
            {selectedIssueId && issueQuery.data && (
              <IssueDetail issue={issueQuery.data} onSelectEvidence={setSelectedEvidenceId} />
            )}
          </div>
        </div>
      )}

      <EvidenceDrawer evidenceId={selectedEvidenceId} onClose={() => setSelectedEvidenceId(null)} />
    </div>
  );
}
