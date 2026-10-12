import { describe, expect, it } from "vitest";
import { formatBytes, formatPercent, formatPkr } from "./format";

describe("formatPkr", () => {
  it("formats a PKR amount with no decimals", () => {
    expect(formatPkr(125000)).toContain("125,000");
  });
});

describe("formatPercent", () => {
  it("formats a fraction as a percentage", () => {
    expect(formatPercent(0.1725)).toBe("17.3%");
  });
});

describe("formatBytes", () => {
  it("formats small byte counts as bytes", () => {
    expect(formatBytes(500)).toBe("500 B");
  });

  it("formats larger byte counts with a unit", () => {
    expect(formatBytes(1_500_000)).toBe("1.4 MB");
  });
});
