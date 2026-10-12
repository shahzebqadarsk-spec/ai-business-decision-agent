import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KpiCard } from "./KpiCard";
import type { KpiResult } from "../../types/kpi";

function makeResult(overrides: Partial<KpiResult>): KpiResult {
  return {
    kpi_id: "gross_profit",
    name: "Gross Profit",
    unit: "currency",
    currency: "PKR",
    granularity: "year",
    period_key: "2024",
    status: "available",
    status_reason: null,
    value: 100,
    comparison_type: null,
    comparison_period_key: null,
    comparison_value: null,
    absolute_change: null,
    percentage_change: null,
    percentage_change_status: "not_requested",
    data_coverage: {},
    source_file_ids: [],
    source_fields: [],
    calculation_version: "1.0.0",
    calculated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("KpiCard", () => {
  it("never renders a fabricated zero when the KPI cannot be computed", () => {
    render(
      <KpiCard
        result={makeResult({
          status: "cannot_compute",
          value: null,
          status_reason: "Required canonical table(s) not yet materialized: fact_expenses.",
        })}
      />,
    );
    expect(screen.queryByText("PKR 0")).not.toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText(/fact_expenses/)).toBeInTheDocument();
  });

  it("shows insufficient-data status with its reason rather than a number", () => {
    render(
      <KpiCard
        result={makeResult({
          status: "insufficient_data",
          value: null,
          status_reason: "No fact_sales rows found for period 2099.",
        })}
      />,
    );
    expect(screen.getByText("Insufficient data")).toBeInTheDocument();
    expect(screen.getByText(/2099/)).toBeInTheDocument();
  });

  it("renders the formatted value and comparison direction when available", () => {
    render(
      <KpiCard
        result={makeResult({
          value: 716_049_599.27,
          comparison_type: "YoY",
          comparison_value: 557_004_208.87,
          percentage_change: 28.55,
        })}
      />,
    );
    expect(screen.getByText(/YoY/)).toBeInTheDocument();
    expect(screen.getByText(/28\.6%/)).toBeInTheDocument();
  });
});
