import type { ReactNode } from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { SeverityBadge } from "./SeverityBadge";
import { ContributionBarChart } from "./ContributionBarChart";
import { WaterfallChart } from "./WaterfallChart";
import { formatCount, formatPercentValue, formatPkr, formatSigned } from "../../lib/format";
import { useAnalyzeIssue } from "../../hooks/useRca";
import type { ContributionBreakdownPayload, GrossProfitPayload, Issue, VolumePriceEffectPayload } from "../../types/rca";

const SECTION_LABELS: Record<string, string> = {
  by_region: "Revenue contribution by region",
  by_product: "Revenue contribution by product",
  by_customer: "Revenue contribution by customer",
  by_product_within_region: "Product contribution within this region",
  by_customer_within_region: "Customer contribution within this region",
  cogs_by_product: "COGS contribution by product",
  cogs_by_region: "COGS contribution by region",
  volume_price_effect: "Volume / price effect on revenue",
  volume_price_effect_within_region: "Volume / price effect within this region",
  gross_profit: "Gross profit decomposition (revenue effect vs COGS effect)",
};

const SKIP_KEYS = new Set(["region", "product", "contribution_evidence_id"]);

function titleCase(key: string): string {
  return SECTION_LABELS[key] ?? key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function unitForKey(key: string): "currency" | "percentage" | "quantity" | "plain" {
  if (key.includes("pct")) return "percentage";
  if (key.includes("quantity")) return "quantity";
  if (key.includes("price") || key.includes("revenue") || key.includes("cogs") || key.includes("gross_profit")) {
    return "currency";
  }
  return "plain";
}

function formatByUnit(value: number, unit: ReturnType<typeof unitForKey>): string {
  if (unit === "currency") return formatPkr(value);
  if (unit === "percentage") return formatPercentValue(value);
  if (unit === "quantity") return formatCount(value);
  return value.toFixed(2);
}

function isBreakdownPayload(obj: Record<string, unknown>): boolean {
  return Array.isArray(obj.rows);
}

function FactPairRow({
  label,
  current,
  prior,
  evidenceId,
  unit,
  onSelectEvidence,
}: {
  label: string;
  current: number | null;
  prior: number | null;
  evidenceId: string | undefined;
  unit: ReturnType<typeof unitForKey>;
  onSelectEvidence: (id: string) => void;
}) {
  return (
    <tr className="border-b border-slate-100 last:border-0">
      <td className="py-1.5 text-slate-500">{label}</td>
      <td className="py-1.5 text-right text-slate-700">{prior !== null ? formatByUnit(prior, unit) : "—"}</td>
      <td className="py-1.5 text-right font-medium text-slate-900">
        {current !== null ? formatByUnit(current, unit) : "—"}
      </td>
      <td className="py-1.5 text-right">
        {evidenceId && (
          <button
            type="button"
            onClick={() => onSelectEvidence(evidenceId)}
            className="text-xs text-blue-600 underline hover:text-blue-800"
          >
            Evidence
          </button>
        )}
      </td>
    </tr>
  );
}

function renderSection(key: string, value: unknown, onSelectEvidence: (id: string) => void): ReactNode {
  if (value === null || value === undefined || SKIP_KEYS.has(key)) return null;

  if (typeof value === "string") {
    return (
      <p key={key} className="text-sm text-slate-500">
        <span className="font-medium text-slate-700">{titleCase(key)}:</span> {value}
      </p>
    );
  }

  if (typeof value === "number") {
    return (
      <p key={key} className="text-sm text-slate-500">
        <span className="font-medium text-slate-700">{titleCase(key)}:</span>{" "}
        {formatByUnit(value, unitForKey(key))}
      </p>
    );
  }

  if (typeof value !== "object") return null;
  const obj = value as Record<string, unknown>;

  if (isBreakdownPayload(obj)) {
    return (
      <ContributionBarChart
        key={key}
        title={titleCase(key)}
        breakdown={obj as unknown as ContributionBreakdownPayload}
        onSelectEvidence={onSelectEvidence}
      />
    );
  }

  if ("volume_effect" in obj && "price_effect" in obj) {
    const vp = obj as unknown as VolumePriceEffectPayload;
    return (
      <WaterfallChart
        key={key}
        title={titleCase(key)}
        steps={[
          { label: "Volume effect", value: vp.volume_effect, evidenceId: vp.evidence_ids[0] },
          { label: "Price effect", value: vp.price_effect, evidenceId: vp.evidence_ids[1] },
        ]}
        total={vp.total_change}
        totalLabel="Revenue change"
        onSelectEvidence={onSelectEvidence}
      />
    );
  }

  if ("revenue_effect" in obj && "cogs_effect" in obj) {
    const gp = obj as unknown as GrossProfitPayload;
    return (
      <WaterfallChart
        key={key}
        title={titleCase(key)}
        steps={[
          { label: "Revenue effect", value: gp.revenue_effect, evidenceId: gp.evidence_ids[0] },
          { label: "COGS effect", value: gp.cogs_effect, evidenceId: gp.evidence_ids[1] },
        ]}
        total={gp.total_change}
        totalLabel="Gross profit change"
        onSelectEvidence={onSelectEvidence}
      />
    );
  }

  if ("current" in obj && "prior" in obj && "evidence_id" in obj) {
    return (
      <Card key={key}>
        <h4 className="mb-2 text-sm font-semibold text-slate-600">{titleCase(key)}</h4>
        <table className="w-full text-left text-sm">
          <tbody>
            <FactPairRow
              label={titleCase(key)}
              current={obj.current as number | null}
              prior={obj.prior as number | null}
              evidenceId={obj.evidence_id as string}
              unit={unitForKey(key)}
              onSelectEvidence={onSelectEvidence}
            />
          </tbody>
        </table>
      </Card>
    );
  }

  return null;
}

export function IssueDetail({
  issue,
  onSelectEvidence,
}: {
  issue: Issue;
  onSelectEvidence: (evidenceId: string) => void;
}) {
  const analyzeMutation = useAnalyzeIssue();

  const changeDirection =
    issue.percentage_change === null ? null : issue.percentage_change >= 0 ? "up" : "down";
  const changeColor = changeDirection === "up" ? "text-emerald-700" : "text-red-700";

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-900">{issue.title}</h3>
            <p className="mt-1 text-xs text-slate-400">
              {issue.issue_type.replace(/_/g, " ")} &middot; {issue.period_key}
              {issue.comparison_period_key && ` vs ${issue.comparison_period_key}`}
            </p>
          </div>
          <SeverityBadge severity={issue.severity} />
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <p className="text-xs text-slate-400">Prior</p>
            <p className="text-sm font-medium text-slate-700">
              {issue.prior_value !== null ? formatByUnit(issue.prior_value, unitForKey(issue.metric)) : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Current</p>
            <p className="text-sm font-medium text-slate-900">
              {issue.current_value !== null ? formatByUnit(issue.current_value, unitForKey(issue.metric)) : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Absolute change</p>
            <p className={`text-sm font-medium ${changeColor}`}>
              {issue.absolute_change !== null
                ? formatSigned(issue.absolute_change, (v) => formatByUnit(v, unitForKey(issue.metric)))
                : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Percentage change</p>
            <p className={`text-sm font-medium ${changeColor}`}>
              {issue.percentage_change !== null ? formatSigned(issue.percentage_change, formatPercentValue) : "—"}
            </p>
          </div>
        </div>

        {issue.status === "detected" && (
          <button
            type="button"
            onClick={() => analyzeMutation.mutate(issue.id)}
            disabled={analyzeMutation.isPending}
            className="mt-4 rounded bg-slate-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {analyzeMutation.isPending ? "Analyzing..." : "Run driver analysis"}
          </button>
        )}
        {analyzeMutation.isError && (
          <p className="mt-2 text-xs text-red-600">Could not run driver analysis for this issue.</p>
        )}
      </Card>

      <Card>
        <h4 className="mb-2 text-sm font-semibold text-slate-600">Materiality</h4>
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="text-slate-400">
              <th className="py-1 font-medium">Rule</th>
              <th className="py-1 text-right font-medium">Threshold</th>
              <th className="py-1 text-right font-medium">Actual</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(issue.materiality).map(([name, rule]) => (
              <tr key={name} className="border-t border-slate-100">
                <td className="py-1 text-slate-600">{name.replace(/_/g, " ")}</td>
                <td className="py-1 text-right text-slate-500">{rule.threshold}</td>
                <td className="py-1 text-right font-medium text-slate-800">{rule.actual.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {issue.status === "analyzed" && issue.decomposition && (
        <div className="space-y-4">
          <Card className="border-amber-200 bg-amber-50">
            <p className="text-xs text-amber-800">
              <Badge className="mr-1 bg-amber-200 text-amber-900">Driver analysis</Badge>
              Every figure below is a measured contribution or association, not proof of causation.
              Click any bar or value to see the Evidence record behind it.
            </p>
          </Card>
          {Object.entries(issue.decomposition).map(([key, value]) => renderSection(key, value, onSelectEvidence))}
        </div>
      )}
    </div>
  );
}
