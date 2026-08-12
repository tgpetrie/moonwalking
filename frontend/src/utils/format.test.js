import { describe, expect, it } from "vitest";
import { formatPrice, formatPct } from "./format.js";

describe("formatPrice", () => {
  it("returns fallback for null (not '$0')", () => {
    expect(formatPrice(null)).toBe("—");
  });

  it("returns fallback for undefined", () => {
    expect(formatPrice(undefined)).toBe("—");
  });

  it("returns fallback for empty string", () => {
    expect(formatPrice("")).toBe("—");
  });

  it("returns fallback for 0 (not '$0')", () => {
    expect(formatPrice(0)).toBe("—");
  });

  it("formats a tiny coin price like 0.00226", () => {
    const result = formatPrice(0.00226);
    expect(result).toBe("$0.00226");
  });

  it("formats 0.0314 with sufficient decimals", () => {
    const result = formatPrice(0.0314);
    expect(result).toBe("$0.0314");
  });

  it("formats sub-penny prices without scientific notation", () => {
    const result = formatPrice(0.000123);
    expect(result).toMatch(/^\$0\.000123/);
    expect(result).not.toMatch(/e/i);
  });

  it("formats mid-range price like 1.2345", () => {
    const result = formatPrice(1.2345);
    expect(result).toBe("$1.234");
  });

  it("formats a large price like 123.45", () => {
    const result = formatPrice(123.45);
    expect(result).toBe("$123.45");
  });

  it("uses custom fallback option", () => {
    expect(formatPrice(null, { fallback: "N/A" })).toBe("N/A");
  });

  it("parses dollar-sign strings", () => {
    const result = formatPrice("$0.00226");
    expect(result).toBe("$0.00226");
  });
});

describe("formatPct", () => {
  it("formats a positive percent with sign", () => {
    expect(formatPct(12.4)).toBe("+12.4%");
  });

  it("formats a negative percent", () => {
    expect(formatPct(-6.8)).toBe("-6.8%");
  });

  it("returns fallback for null", () => {
    expect(formatPct(null)).toBe("—");
  });

  it("omits sign when sign:false", () => {
    expect(formatPct(5.5, { sign: false })).toBe("5.5%");
  });
});
