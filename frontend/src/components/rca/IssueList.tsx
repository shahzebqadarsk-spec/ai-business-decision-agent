import { Card } from "../ui/card";
import { SeverityBadge } from "./SeverityBadge";
import type { Issue } from "../../types/rca";

export function IssueList({
  issues,
  selectedId,
  onSelect,
}: {
  issues: Issue[];
  selectedId: string | null;
  onSelect: (issueId: string) => void;
}) {
  if (issues.length === 0) {
    return (
      <Card>
        <p className="text-sm text-slate-400">
          No material issues detected for this period yet. Run detection above.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-0">
      <ul className="divide-y divide-slate-100">
        {issues.map((issue) => (
          <li key={issue.id}>
            <button
              type="button"
              onClick={() => onSelect(issue.id)}
              className={`flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-slate-50 ${
                selectedId === issue.id ? "bg-slate-50" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-slate-800">{issue.title}</span>
                <SeverityBadge severity={issue.severity} />
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span>{issue.issue_type.replace(/_/g, " ")}</span>
                <span>&middot;</span>
                <span>{issue.period_key}</span>
                <span>&middot;</span>
                <span>{issue.status}</span>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
