import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ContributionBarChart } from "./ContributionBarChart";
import type { ContributionBreakdownPayload } from "../../types/rca";

function makeBreakdown(overrides: Partial<ContributionBreakdownPayload> = {}): ContributionBreakdownPayload {
  return {
    total_change: -13_860_000,
    current_total: 70_000_000,
    prior_total: 83_860_000,
    coverage_pct: 100.0,
    residual_absolute: 0.0,
    residual_is_material: false,
    rows: [
      {
        dimension_value: "REG-05",
        current_value: 10_000_000,
        prior_value: 23_860_000,
        absolute_contribution: -13_860_000,
        percentage_contribution: 100.0,
        direction: "negative",
        rank: 1,
        current_share_pct: 14.3,
        is_other_bucket: false,
        other_bucket_count: null,
        evidence_id: "e-0001",
      },
    ],
    ...overrides,
  };
}

// Phase 4 spec section 9: statistical contribution must never be presented as causation. This
// mirrors the KpiCard test's pattern of asserting an absence rather than a positive render.
describe("ContributionBarChart", () => {
  it("never uses causal language, only association/contribution phrasing", () => {
    render(
      <ContributionBarChart title="Revenue contribution by region" breakdown={makeBreakdown()} onSelectEvidence={vi.fn()} />,
    );
    const container = screen.getByText(/measured association/i).closest("div");
    expect(container?.textContent ?? "").not.toMatch(/\bcaused\b|\broot cause\b|\bbecause of\b/i);
    expect(screen.getByText(/measured association, not a causal claim/i)).toBeInTheDocument();
  });

  it("surfaces a material-residual warning when the breakdown does not fully explain the change", () => {
    render(
      <ContributionBarChart
        title="Revenue contribution by region"
        breakdown={makeBreakdown({ residual_is_material: true, residual_absolute: 2_000_000 })}
        onSelectEvidence={vi.fn()}
      />,
    );
    expect(screen.getByText(/Material unexplained residual/i)).toBeInTheDocument();
  });

  it("shows the coverage percentage explained by the breakdown", () => {
    render(
      <ContributionBarChart title="Revenue contribution by region" breakdown={makeBreakdown()} onSelectEvidence={vi.fn()} />,
    );
    expect(screen.getByText(/100\.0% explained/)).toBeInTheDocument();
  });
});
