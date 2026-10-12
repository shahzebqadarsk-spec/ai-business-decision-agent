import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { formatKpiValue, formatPercentValue } from "../../lib/format";
import type { KpiResult } from "../../types/kpi";

const STATUS_LABEL: Record<string, string> = {
  cannot_compute: "Unavailable",
  insufficient_data: "Insufficient data",
  invalid_data: "Undefined",
};

export function KpiCard({ result }: { result: KpiResult }) {
  if (result.status !== "available" || result.value === null) {
    return (
      <Card>
        <h3 className="text-sm font-medium text-slate-500">{result.name}</h3>
        <p className="mt-2 text-lg font-semibold text-slate-400">{STATUS_LABEL[result.status] ?? result.status}</p>
        {result.status_reason && <p className="mt-1 text-xs text-slate-400">{result.status_reason}</p>}
      </Card>
    );
  }

  const direction =
    result.percentage_change === null ? null : result.percentage_change >= 0 ? "up" : "down";
  const directionColor = direction === "up" ? "text-emerald-700" : direction === "down" ? "text-red-700" : "";
  const arrow = direction === "up" ? "↑" : direction === "down" ? "↓" : "";

  return (
    <Card>
      <h3 className="text-sm font-medium text-slate-500">{result.name}</h3>
      <p className="mt-1 text-2xl font-semibold text-slate-900">
        {formatKpiValue(result.value, result.unit, result.currency)}
      </p>
      {result.comparison_type && (
        <p className="mt-1 text-xs">
          {result.percentage_change !== null ? (
            <span className={directionColor}>
              {arrow} {formatPercentValue(Math.abs(result.percentage_change))} {result.comparison_type}
            </span>
          ) : (
            <Badge className="bg-slate-100 text-slate-500">
              {result.comparison_value === null ? "No comparison data" : "Change undefined"}
            </Badge>
          )}
          {result.comparison_value !== null && (
            <span className="ml-1 text-slate-400">
              (vs {formatKpiValue(result.comparison_value, result.unit, result.currency)})
            </span>
          )}
        </p>
      )}
    </Card>
  );
}
