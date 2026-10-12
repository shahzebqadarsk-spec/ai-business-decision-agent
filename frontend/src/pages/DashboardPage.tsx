import { useState } from "react";
import { Card } from "../components/ui/card";
import { KpiCard } from "../components/dashboard/KpiCard";
import { BreakdownBarChart } from "../components/dashboard/BreakdownBarChart";
import { RevenueTrendChart } from "../components/dashboard/RevenueTrendChart";
import { CustomerTable } from "../components/dashboard/CustomerTable";
import { useDashboard } from "../hooks/useKpi";

export function DashboardPage() {
  const [periodKey, setPeriodKey] = useState<string | undefined>(undefined);
  const dashboardQuery = useDashboard(periodKey, "YoY");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Executive Dashboard</h2>
        <label className="flex items-center gap-2 text-sm text-slate-500">
          Year:
          <input
            type="text"
            placeholder={dashboardQuery.data?.period_key ?? "latest"}
            defaultValue=""
            onBlur={(e) => setPeriodKey(e.target.value.trim() || undefined)}
            className="w-20 rounded border border-slate-300 px-2 py-1 text-sm"
          />
        </label>
      </div>

      {dashboardQuery.isLoading && <Card><p className="text-sm text-slate-500">Loading dashboard...</p></Card>}
      {dashboardQuery.isError && (
        <Card>
          <p className="text-sm text-red-600">Could not reach the backend.</p>
        </Card>
      )}

      {dashboardQuery.data && (
        <>
          <p className="text-xs text-slate-400">
            Showing {dashboardQuery.data.period_key} vs {dashboardQuery.data.comparison_type} comparison period.
          </p>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {dashboardQuery.data.cards.map((card) => (
              <KpiCard key={card.kpi_id} result={card} />
            ))}
          </div>

          <RevenueTrendChart rows={dashboardQuery.data.revenue_trend} />

          <div className="grid gap-4 lg:grid-cols-2">
            <BreakdownBarChart title="Revenue by region" rows={dashboardQuery.data.revenue_by_region} />
            <BreakdownBarChart title="Revenue by product" rows={dashboardQuery.data.revenue_by_product} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <CustomerTable title="Top 5 customers" rows={dashboardQuery.data.top_customers} />
            <CustomerTable title="Bottom 5 customers" rows={dashboardQuery.data.bottom_customers} />
          </div>
        </>
      )}
    </div>
  );
}
