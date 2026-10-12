import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DatasetList } from "./DatasetList";

function renderWithClient() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <DatasetList selectedDatasetId={null} onSelect={() => {}} />
    </QueryClientProvider>,
  );
}

describe("DatasetList", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify([
            { id: "d1", name: "Q1 sales export", status: "profiled", created_at: "2026-01-01T00:00:00Z" },
          ]),
          { status: 200 },
        ),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders datasets returned by the backend with their status", async () => {
    renderWithClient();
    await waitFor(() => expect(screen.getByText("Q1 sales export")).toBeInTheDocument());
    expect(screen.getByText("profiled")).toBeInTheDocument();
  });
});
