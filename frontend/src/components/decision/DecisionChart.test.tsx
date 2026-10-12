import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DecisionChart } from "./DecisionChart";
import type { DecisionOption } from "../../types/decision";

function makeOptions(): DecisionOption[] {
  return [
    {
      id: "o-0001",
      decision_run_id: "run-0001",
      scenario_id: "s-0001",
      title: "Growth push",
      score: 0.42,
      rank: 1,
      criteria_breakdown: { growth: { weight: 1, value: 42, weighted: 0.42 } },
      rationale: "Ranked 1 of 2 scored options...",
      evidence_id: "e-0001",
    },
    {
      id: "o-0002",
      decision_run_id: "run-0001",
      scenario_id: "s-0002",
      title: "Cost discipline",
      score: 0.1,
      rank: 2,
      criteria_breakdown: { growth: { weight: 1, value: 10, weighted: 0.1 } },
      rationale: "Ranked 2 of 2 scored options...",
      evidence_id: "e-0002",
    },
  ];
}

describe("DecisionChart", () => {
  it("renders a chart heading when scored options exist", () => {
    // Recharts' ResponsiveContainer never gets real dimensions under jsdom, so (as in
    // ForecastChart/ScenarioChart's own tests) this only asserts on the static heading, not on
    // anything rendered inside the chart's SVG.
    render(<DecisionChart options={makeOptions()} />);
    expect(screen.getByText(/composite score by option/i)).toBeInTheDocument();
  });

  it("shows a 'no scored options' message when nothing is scored", () => {
    const unscored: DecisionOption[] = [
      {
        id: "o-0003",
        decision_run_id: "run-0001",
        scenario_id: "s-0003",
        title: "Unscored",
        score: null,
        rank: null,
        criteria_breakdown: { growth: { weight: 1, value: null } },
        rationale: "Not scored: no scenario data for growth.",
        evidence_id: null,
      },
    ];
    render(<DecisionChart options={unscored} />);
    expect(screen.getByText(/no scored options to chart yet/i)).toBeInTheDocument();
  });
});
