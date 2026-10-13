import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "../ui/card";
import { formatCurrencyAmount } from "../../lib/format";
import { useSystemConfig } from "../../hooks/useSystemStatus";
import type { DimensionBreakdownRow } from "../../types/kpi";

export function BreakdownBarChart({
  title,
  rows,
}: {
  title: string;
  rows: DimensionBreakdownRow[];
}) {
  const systemConfigQuery = useSystemConfig();
  const currency = systemConfigQuery.data?.currency ?? null;
  const fmt = (v: number) => formatCurrencyAmount(v, currency);
  const data = rows
    .filter((r) => r.value !== null)
    .map((r) => ({ label: r.dimension_value ?? "(unknown)", value: r.value as number }));

  if (data.length === 0) {
    return (
      <Card>
        <h3 className="mb-2 text-sm font-semibold text-slate-500">{title}</h3>
        <p className="text-sm text-slate-400">No data available for this breakdown.</p>
      </Card>
    );
  }

  return (
    <Card>
      <h3 className="mb-2 text-sm font-semibold text-slate-500">{title}</h3>
      <ResponsiveContainer width="100%" height={Math.max(180, data.length * 32)}>
        <BarChart data={data} layout="vertical" margin={{ left: 24, right: 16, top: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tickFormatter={(v: number) => fmt(v)} fontSize={11} />
          <YAxis type="category" dataKey="label" width={70} fontSize={12} />
          <Tooltip formatter={(v: number) => fmt(v)} />
          <Bar dataKey="value" fill="#1d4ed8" radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
