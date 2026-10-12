import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MappingReview } from "./MappingReview";

function renderWithClient() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MappingReview fileId="file-1" />
    </QueryClientProvider>,
  );
}

describe("MappingReview", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.includes("/canonical-fields/")) {
          return new Response(
            JSON.stringify([
              { name: "customer_id", required: true, data_type: "identifier" },
              { name: "month", required: true, data_type: "date" },
            ]),
            { status: 200 },
          );
        }
        if (url.includes("/mappings")) {
          return new Response(
            JSON.stringify([
              {
                id: "m1",
                source_column: "cust_id",
                proposed_canonical_field: "customer_id",
                confidence: 1.0,
                method: "rule",
                reason: "synonym match",
                status: "proposed",
                confirmed_canonical_field: null,
                confirmed_by: null,
              },
              {
                id: "m2",
                source_column: "unit_cost_pkr",
                proposed_canonical_field: null,
                confidence: 0.0,
                method: "rule",
                reason: null,
                status: "unresolved",
                confirmed_canonical_field: null,
                confirmed_by: null,
              },
            ]),
            { status: 200 },
          );
        }
        return new Response("not found", { status: 404 });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows proposed and unresolved mappings distinctly, never auto-confirmed", async () => {
    renderWithClient();
    await waitFor(() => expect(screen.getByText("cust_id")).toBeInTheDocument());

    expect(screen.getByText("proposed")).toBeInTheDocument();
    expect(screen.getByText("unresolved")).toBeInTheDocument();
    // Neither mapping starts out confirmed -- there is no "confirmed" status badge yet.
    expect(screen.queryByText("confirmed")).not.toBeInTheDocument();
  });

  it("disables confirming a mapping until a canonical field is chosen for unresolved rows", async () => {
    renderWithClient();
    await waitFor(() => expect(screen.getByText("unit_cost_pkr")).toBeInTheDocument());

    const confirmButtons = screen.getAllByRole("button", { name: "Confirm" });
    // The unresolved row (second) has no proposed field pre-selected, so confirming is disabled.
    expect(confirmButtons[1]).toBeDisabled();
  });
});
