import { Card } from "../ui/card";
import { formatCurrencyAmount } from "../../lib/format";
import { useDisplayCurrency } from "../../hooks/useCurrency";
import type { DimensionBreakdownRow } from "../../types/kpi";

export function CustomerTable({
  title,
  rows,
}: {
  title: string;
  rows: DimensionBreakdownRow[];
}) {
  const currency = useDisplayCurrency();
  return (
    <Card>
      <h3 className="mb-2 text-sm font-semibold text-slate-500">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-sm text-slate-400">No data available.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <tbody>
            {rows.map((row) => (
              <tr key={row.dimension_value} className="border-b border-slate-100 last:border-0">
                <td className="py-1.5 text-slate-700">{row.dimension_value ?? "(unknown)"}</td>
                <td className="py-1.5 text-right font-medium text-slate-900">
                  {row.value !== null ? formatCurrencyAmount(row.value, currency) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
