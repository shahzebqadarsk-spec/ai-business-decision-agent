import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TypeBadge } from "./TypeBadge";

describe("TypeBadge", () => {
  it("renders the fact label", () => {
    render(<TypeBadge type="fact" />);
    expect(screen.getByText("fact")).toBeInTheDocument();
  });

  it("renders the recommendation label", () => {
    render(<TypeBadge type="recommendation" />);
    expect(screen.getByText("recommendation")).toBeInTheDocument();
  });
});
