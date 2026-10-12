import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScenarioChart } from "./ScenarioChart";
import type { ScenarioResult } from "../../types/scenario";

function makeResults(): ScenarioResult[] {
  return [
    {
      id: "r-0001",
      scenario_id: "s-0001",
      metric: "revenue",
      period_key: "2026-01",
      horizon_index: 1,
      baseline_value: 1_000_000,
      scenario_value: 1_100_000,
      delta_absolute: 100_000,
      delta_percentage: 10.0,
    },
    {
      id: "r-0002",
      scenario_id: "s-0001",
      metric: "cogs",
      period_key: "2026-01",
      horizon_index: 1,
      baseline_value: 500_000,
      scenario_value: 500_000,
      delta_absolute: 0,
      delta_percentage: 0,
    },
  ];
}

describe("ScenarioChart", () => {
  it("renders baseline vs. scenario for the requested metric", () => {
    render(<ScenarioChart metric="revenue" results={makeResults()} />);
    expect(screen.getByText(/revenue: baseline vs\. scenario/i)).toBeInTheDocument();
  });

  it("shows a 'no results' message when the scenario has nothing for this metric", () => {
    render(<ScenarioChart metric="gross_margin_pct" results={makeResults()} />);
    expect(screen.getByText(/no gross_margin_pct results in this scenario/i)).toBeInTheDocument();
  });
});
