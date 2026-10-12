import { Card } from "../ui/card";
import { StatusBadge } from "./StatusBadge";
import { useQualityIssues } from "../../hooks/useIngestion";

export function QualityIssuesList({ fileId }: { fileId: string }) {
  const issuesQuery = useQualityIssues(fileId);

  return (
    <Card>
      <h2 className="mb-3 text-sm font-semibold text-slate-500">Data-quality issues</h2>
      {issuesQuery.isLoading && <p className="text-sm text-slate-500">Checking data quality...</p>}
      {issuesQuery.isError && <p className="text-sm text-red-600">Could not load quality issues.</p>}
      {issuesQuery.data && issuesQuery.data.length === 0 && (
        <p className="text-sm text-emerald-700">No issues detected in this file.</p>
      )}

      <ul className="space-y-2">
        {issuesQuery.data?.map((issue) => (
          <li key={issue.id} className="rounded border border-slate-100 p-2 text-sm">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="font-medium text-slate-800">
                {issue.issue_type.replaceAll("_", " ")}
                {issue.column_name ? ` · ${issue.column_name}` : ""}
              </span>
              <StatusBadge status={issue.severity} />
            </div>
            <p className="text-slate-600">{issue.description}</p>
            {issue.affected_row_count !== null && (
              <p className="mt-0.5 text-xs text-slate-500">
                {issue.affected_row_count.toLocaleString()} row(s) affected
              </p>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
