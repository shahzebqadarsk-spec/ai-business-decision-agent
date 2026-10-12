import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "./components/AppShell";
import { StatusPage } from "./pages/StatusPage";
import { ChartCheckPage } from "./pages/ChartCheckPage";
import { IngestionPage } from "./pages/IngestionPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DriverAnalysisPage } from "./pages/DriverAnalysisPage";
import { ForecastPage } from "./pages/ForecastPage";
import { ScenarioPage } from "./pages/ScenarioPage";
import { DecisionPage } from "./pages/DecisionPage";

const queryClient = new QueryClient();

type View = "dashboard" | "issues" | "forecast" | "scenario" | "decision" | "ingestion" | "system";

const TABS: { id: View; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "issues", label: "Issues & Driver Analysis" },
  { id: "forecast", label: "Forecasting" },
  { id: "scenario", label: "Scenario / What-If" },
  { id: "decision", label: "Decisions" },
  { id: "ingestion", label: "Data ingestion" },
  { id: "system", label: "System status" },
];

export function App() {
  const [view, setView] = useState<View>("dashboard");

  return (
    <QueryClientProvider client={queryClient}>
      <AppShell>
        <nav className="mb-4 flex gap-1 border-b border-slate-200">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setView(tab.id)}
              className={`px-3 py-1.5 text-sm ${
                view === tab.id ? "border-b-2 border-slate-800 font-medium text-slate-900" : "text-slate-500"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {view === "dashboard" && <DashboardPage />}
        {view === "issues" && <DriverAnalysisPage />}
        {view === "forecast" && <ForecastPage />}
        {view === "scenario" && <ScenarioPage />}
        {view === "decision" && <DecisionPage />}
        {view === "ingestion" && <IngestionPage />}
        {view === "system" && (
          <div className="space-y-6">
            <StatusPage />
            <ChartCheckPage />
          </div>
        )}
      </AppShell>
    </QueryClientProvider>
  );
}
