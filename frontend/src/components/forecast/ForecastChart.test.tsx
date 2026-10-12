import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ForecastChart } from "./ForecastChart";
import type { ForecastPoint } from "../../types/forecast";

function makeForecasts(): ForecastPoint[] {
  return [
    {
      id: "f-0001",
      forecast_run_id: "run-0001",
      metric: "revenue",
      period_key: "2026-01",
      horizon_index: 1,
      point_estimate: 1_000_000,
      lower_bound: 900_000,
      upper_bound: 1_100_000,
      evidence_id: "e-0001",
    },
    {
      id: "f-0002",
      forecast_run_id: "run-0001",
      metric: "revenue",
      period_key: "2026-02",
      horizon_index: 2,
      point_estimate: 1_050_000,
      lower_bound: 800_000,
      upper_bound: 1_300_000,
      evidence_id: "e-0002",
    },
  ];
}

// Phase 5 spec: a forecast is an inference, never a fact or a guaranteed outcome, and the
// prediction interval must visibly widen the further into the future a point sits -- this
// mirrors the RCA ContributionBarChart test's pattern of asserting the required caveat text.
describe("ForecastChart", () => {
  it("labels the shaded region as a prediction interval, never a fact", () => {
    render(
      <ForecastChart
        metric="revenue"
        confidenceLevel={0.8}
        historical={[{ dimension_value: "2025-12", value: 950_000 }]}
        forecasts={makeForecasts()}
      />,
    );
    expect(screen.getByText(/not a fact and not a guaranteed outcome/i)).toBeInTheDocument();
    expect(screen.getByText(/80% prediction interval/i)).toBeInTheDocument();
  });

  it("shows a 'no data' message when there is nothing to chart", () => {
    render(<ForecastChart metric="revenue" confidenceLevel={0.8} historical={[]} forecasts={[]} />);
    expect(screen.getByText(/no data available to chart/i)).toBeInTheDocument();
  });
});
