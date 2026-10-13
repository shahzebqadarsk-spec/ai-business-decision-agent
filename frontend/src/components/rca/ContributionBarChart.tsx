import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "../ui/card";
import { formatCurrencyAmount, formatSigned } from "../../lib/format";
import type { ContributionBreakdownPayload } from "../../types/rca";

const POSITIVE = "#059669";
const NEGATIVE = "#dc2626";
const FLAT = "#94a3b8";

function colorFor(direction: string): string {
  if (direction === "positive") return POSITIVE;
  if (direction === "negative") return NEGATIVE;
  return FLAT;
}

/** Ranked contribution bars (Phase 4 spec section 14) for one dimensional breakdown --
 * region/product/customer contribution to a total change. Clicking a bar opens the Evidence
 * drawer for the row it represents, so every number here is traceable to its Evidence ID. */
export function ContributionBarChart({
  title,
  breakdown,
  currency,
  onSelectEvidence,
}: {
  title: string;
  breakdown: ContributionBreakdownPayload;
  currency?: string | null;
  onSelectEvidence: (evidenceId: string) => void;
}) {
  const fmt = (v: number) => formatCurrencyAmount(v, currency);
  const data = breakdown.rows.map((row) => ({
    label: row.is_other_bucket ? `Other (${row.other_bucket_count})` : row.dimension_value ?? "(unknown)",
    value: row.absolute_contribution,
    direction: row.direction,
    evidenceId: row.evidence_id,
  }));

  return (
    <Card>
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-slate-600">{title}</h4>
        {breakdown.coverage_pct !== null && (
          <span className="text-xs text-slate-400">{breakdown.coverage_pct.toFixed(1)}% explained</span>
        )}
      </div>
      {breakdown.residual_is_material && (
        <p className="mb-2 text-xs font-medium text-amber-600">
          Material unexplained residual: {fmt(breakdown.residual_absolute)}
        </p>
      )}
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 30)}>
        <BarChart data={data} layout="vertical" margin={{ left: 24, right: 16, top: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tickFormatter={(v: number) => formatSigned(v, fmt)} fontSize={11} />
          <YAxis type="category" dataKey="label" width={80} fontSize={12} />
          <Tooltip
            formatter={(v: number) => formatSigned(v, fmt)}
            labelFormatter={(label: string) => label}
          />
          <Bar
            dataKey="value"
            radius={[0, 3, 3, 0]}
            onClick={(point: { evidenceId?: string }) => {
              if (point?.evidenceId) onSelectEvidence(point.evidenceId);
            }}
            cursor="pointer"
          >
            {data.map((d, i) => (
              <Cell key={i} fill={colorFor(d.direction)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-slate-400">
        Click a bar to see its Evidence record. Contribution is a measured association, not a causal claim.
      </p>
    </Card>
  );
}
