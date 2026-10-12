import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "../ui/card";
import { formatPkr, formatSigned } from "../../lib/format";

const POSITIVE = "#059669";
const NEGATIVE = "#dc2626";
const TOTAL_COLOR = "#1d4ed8";

export interface WaterfallStep {
  label: string;
  value: number;
  evidenceId?: string;
}

interface WaterfallBar {
  label: string;
  base: number;
  size: number;
  value: number;
  evidenceId: string | undefined;
  isTotal: boolean;
}

function buildBars(steps: WaterfallStep[], total: number, totalLabel: string): WaterfallBar[] {
  let running = 0;
  const bars: WaterfallBar[] = steps.map((step) => {
    const before = running;
    running += step.value;
    return {
      label: step.label,
      base: Math.min(before, running),
      size: Math.abs(step.value),
      value: step.value,
      evidenceId: step.evidenceId,
      isTotal: false,
    };
  });
  bars.push({
    label: totalLabel,
    base: Math.min(0, total),
    size: Math.abs(total),
    value: total,
    evidenceId: undefined,
    isTotal: true,
  });
  return bars;
}

function WaterfallTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: WaterfallBar }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0]?.payload;
  if (!item) return null;
  return (
    <div className="rounded border border-slate-200 bg-white px-2 py-1 text-xs shadow-sm">
      <p className="font-medium text-slate-700">{item.label}</p>
      <p className="text-slate-500">{formatSigned(item.value, formatPkr)}</p>
    </div>
  );
}

/** A floating-bar waterfall for a 2-3-step decomposition that sums exactly to a total (volume
 * effect + price effect = revenue change; revenue effect + COGS effect = gross-profit change --
 * Phase 4 spec section 14). Each step bar can carry an Evidence ID; the total bar cannot, since
 * it is an arithmetic sum of the steps rather than its own Evidence row. */
export function WaterfallChart({
  title,
  steps,
  total,
  totalLabel = "Total change",
  onSelectEvidence,
}: {
  title: string;
  steps: WaterfallStep[];
  total: number;
  totalLabel?: string;
  onSelectEvidence?: (evidenceId: string) => void;
}) {
  const bars = buildBars(steps, total, totalLabel);

  return (
    <Card>
      <h4 className="mb-2 text-sm font-semibold text-slate-600">{title}</h4>
      <ResponsiveContainer width="100%" height={Math.max(160, bars.length * 44)}>
        <BarChart data={bars} layout="vertical" margin={{ left: 24, right: 16, top: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tickFormatter={(v: number) => formatSigned(v, formatPkr)} fontSize={11} />
          <YAxis type="category" dataKey="label" width={100} fontSize={12} />
          <Tooltip content={<WaterfallTooltip />} />
          <Bar dataKey="base" stackId="wf" fill="transparent" isAnimationActive={false} />
          <Bar
            dataKey="size"
            stackId="wf"
            radius={[0, 3, 3, 0]}
            onClick={(point: { evidenceId?: string }) => {
              if (point?.evidenceId && onSelectEvidence) onSelectEvidence(point.evidenceId);
            }}
            cursor={onSelectEvidence ? "pointer" : "default"}
          >
            {bars.map((b, i) => (
              <Cell key={i} fill={b.isTotal ? TOTAL_COLOR : b.value >= 0 ? POSITIVE : NEGATIVE} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-slate-400">
        {steps.map((s) => s.label).join(" + ")} sum exactly to {totalLabel.toLowerCase()}.
      </p>
    </Card>
  );
}
