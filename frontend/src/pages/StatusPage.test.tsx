import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StatusPage } from "./StatusPage";

function renderWithClient() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <StatusPage />
    </QueryClientProvider>,
  );
}

describe("StatusPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url.includes("/system/config")) {
          return new Response(
            JSON.stringify({
              currency: "PKR",
              fiscal_year_start_month: 1,
              default_comparison: "YoY",
              synthetic_data_only: true,
              llm_use_mock: true,
            }),
            { status: 200 },
          );
        }
        return new Response(
          JSON.stringify({ use_mock: true, deepseek_key_present: false, routes: {} }),
          { status: 200 },
        );
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the currency from the backend", async () => {
    renderWithClient();
    await waitFor(() => expect(screen.getByText("PKR")).toBeInTheDocument());
  });
});
