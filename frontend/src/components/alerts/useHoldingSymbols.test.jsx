import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("../../mvp/portfolioApi.js", () => ({
  fetchPortfolio: vi.fn(),
}));

import { fetchPortfolio } from "../../mvp/portfolioApi.js";
import useHoldingSymbols, {
  extractHoldingSymbols,
  __resetHoldingsCacheForTests,
} from "./useHoldingSymbols.js";

beforeEach(() => {
  vi.clearAllMocks();
  __resetHoldingsCacheForTests();
});

describe("extractHoldingSymbols", () => {
  it("keeps non-cash symbols, uppercased, and skips cash and junk rows", () => {
    const set = extractHoldingSymbols({
      holdings: [
        { symbol: "eth", is_cash: false },
        { symbol: "USD", is_cash: true },
        { currency: "sol", is_cash: false }, // currency fallback
        { symbol: "", is_cash: false },
        null,
      ],
    });
    expect([...set].sort()).toEqual(["ETH", "SOL"]);
  });

  it("returns an empty set for missing or malformed snapshots", () => {
    expect(extractHoldingSymbols(null).size).toBe(0);
    expect(extractHoldingSymbols({}).size).toBe(0);
    expect(extractHoldingSymbols({ holdings: "nope" }).size).toBe(0);
  });
});

describe("useHoldingSymbols", () => {
  it("resolves holdings from the existing portfolio client", async () => {
    fetchPortfolio.mockResolvedValue({ holdings: [{ symbol: "BTC", is_cash: false }] });
    const { result } = renderHook(() => useHoldingSymbols());
    await waitFor(() => expect(result.current.has("BTC")).toBe(true));
    expect(fetchPortfolio).toHaveBeenCalledTimes(1);
  });

  it("shares one fetch across mounts via the module cache", async () => {
    fetchPortfolio.mockResolvedValue({ holdings: [{ symbol: "BTC", is_cash: false }] });
    const a = renderHook(() => useHoldingSymbols());
    const b = renderHook(() => useHoldingSymbols());
    await waitFor(() => expect(a.result.current.has("BTC")).toBe(true));
    await waitFor(() => expect(b.result.current.has("BTC")).toBe(true));
    expect(fetchPortfolio).toHaveBeenCalledTimes(1);
  });

  it("swallows failures and yields an empty set", async () => {
    fetchPortfolio.mockRejectedValue(Object.assign(new Error("x"), { status: 401 }));
    const { result } = renderHook(() => useHoldingSymbols());
    await waitFor(() => expect(fetchPortfolio).toHaveBeenCalled());
    expect(result.current.size).toBe(0);
  });

  it("does nothing when disabled", () => {
    renderHook(() => useHoldingSymbols({ enabled: false }));
    expect(fetchPortfolio).not.toHaveBeenCalled();
  });

  it("allows a retry after a failure (in-flight marker is cleared)", async () => {
    fetchPortfolio.mockRejectedValueOnce(Object.assign(new Error("x"), { status: 503 }));
    const first = renderHook(() => useHoldingSymbols());
    await waitFor(() => expect(fetchPortfolio).toHaveBeenCalledTimes(1));
    first.unmount();

    fetchPortfolio.mockResolvedValue({ holdings: [{ symbol: "ETH", is_cash: false }] });
    const second = renderHook(() => useHoldingSymbols());
    await waitFor(() => expect(second.result.current.has("ETH")).toBe(true));
    expect(fetchPortfolio).toHaveBeenCalledTimes(2);
  });
});
