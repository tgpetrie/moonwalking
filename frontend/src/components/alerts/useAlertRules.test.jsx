import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("./alertRulesApi.js", () => ({
  listRules: vi.fn(),
  createRule: vi.fn(),
  pauseRule: vi.fn(),
  resumeRule: vi.fn(),
  deleteRule: vi.fn(),
  listRecommendations: vi.fn(),
  acceptRecommendation: vi.fn(),
  dismissRecommendation: vi.fn(),
  listHistory: vi.fn(),
}));

import * as api from "./alertRulesApi.js";
import useAlertRules from "./useAlertRules.js";

const REC = { id: "rec_1", symbol: "ETH", reason: "why", basis: "portfolio" };
const RULE = { id: "rule_1", symbol: "BTC", status: "active", params: {} };

const authError = () => Object.assign(new Error("Sign in"), { isAuthRequired: true });

beforeEach(() => {
  vi.clearAllMocks();
  api.listRules.mockResolvedValue([]);
  api.listRecommendations.mockResolvedValue([]);
  api.listHistory.mockResolvedValue([]);
});

describe("useAlertRules", () => {
  it("fetches each slice only once", async () => {
    const { result } = renderHook(() => useAlertRules());
    await act(async () => { await result.current.loadRules(); });
    await act(async () => { await result.current.loadRules(); });
    expect(api.listRules).toHaveBeenCalledTimes(1);
  });

  it("refetches when forced", async () => {
    const { result } = renderHook(() => useAlertRules());
    await act(async () => { await result.current.loadRules(); });
    await act(async () => { await result.current.loadRules({ force: true }); });
    expect(api.listRules).toHaveBeenCalledTimes(2);
  });

  it("does not fetch slices the user has not opened", async () => {
    const { result } = renderHook(() => useAlertRules());
    await act(async () => { await result.current.loadRules(); });
    expect(api.listHistory).not.toHaveBeenCalled();
    expect(api.listRecommendations).not.toHaveBeenCalled();
  });

  it("treats 401 as authRequired, not an error", async () => {
    api.listRules.mockRejectedValue(authError());
    const { result } = renderHook(() => useAlertRules());
    await act(async () => { await result.current.loadRules(); });
    await waitFor(() => expect(result.current.authRequired).toBe(true));
    expect(result.current.errors.rules).toBeNull();
  });

  it("records real failures as errors", async () => {
    api.listRules.mockRejectedValue(new Error("Could not reach the server."));
    const { result } = renderHook(() => useAlertRules());
    await act(async () => { await result.current.loadRules(); });
    await waitFor(() =>
      expect(result.current.errors.rules).toBe("Could not reach the server.")
    );
    expect(result.current.authRequired).toBe(false);
  });

  it("removes a dismissed recommendation optimistically", async () => {
    api.listRecommendations.mockResolvedValue([REC]);
    api.dismissRecommendation.mockResolvedValue(true);
    const { result } = renderHook(() => useAlertRules());
    await act(async () => { await result.current.loadRecommendations(); });
    expect(result.current.recommendations).toHaveLength(1);

    await act(async () => { await result.current.dismissRecommendation("rec_1"); });
    expect(result.current.recommendations).toHaveLength(0);
  });

  it("restores the recommendation when dismiss fails", async () => {
    api.listRecommendations.mockResolvedValue([REC]);
    api.dismissRecommendation.mockRejectedValue(new Error("nope"));
    const { result } = renderHook(() => useAlertRules());
    await act(async () => { await result.current.loadRecommendations(); });

    await act(async () => {
      await expect(result.current.dismissRecommendation("rec_1")).rejects.toThrow("nope");
    });
    expect(result.current.recommendations).toHaveLength(1);
    expect(result.current.recommendations[0].id).toBe("rec_1");
  });

  it("flips rule status optimistically and reverts on failure", async () => {
    api.listRules.mockResolvedValue([RULE]);
    api.pauseRule.mockRejectedValue(new Error("nope"));
    const { result } = renderHook(() => useAlertRules());
    await act(async () => { await result.current.loadRules(); });

    await act(async () => {
      await expect(result.current.setRuleStatus("rule_1", "paused")).rejects.toThrow();
    });
    expect(result.current.rules[0].status).toBe("active"); // reverted
  });

  it("restores a deleted rule when the server rejects", async () => {
    api.listRules.mockResolvedValue([RULE]);
    api.deleteRule.mockRejectedValue(new Error("nope"));
    const { result } = renderHook(() => useAlertRules());
    await act(async () => { await result.current.loadRules(); });

    await act(async () => {
      await expect(result.current.removeRule("rule_1")).rejects.toThrow();
    });
    expect(result.current.rules).toHaveLength(1);
  });

  it("moves an accepted recommendation into the rule list", async () => {
    api.listRecommendations.mockResolvedValue([REC]);
    api.acceptRecommendation.mockResolvedValue({ ...RULE, source: "recommended" });
    const { result } = renderHook(() => useAlertRules());
    await act(async () => { await result.current.loadRecommendations(); });

    await act(async () => { await result.current.acceptRecommendation("rec_1"); });
    expect(result.current.recommendations).toHaveLength(0);
    expect(result.current.rules).toHaveLength(1);
  });

  it("does not optimistically add a rule before the server confirms", async () => {
    api.createRule.mockRejectedValue(new Error("Percentage must be 100 or less."));
    const { result } = renderHook(() => useAlertRules());
    await act(async () => {
      await expect(result.current.createRule({ symbol: "BTC" })).rejects.toThrow();
    });
    expect(result.current.rules).toHaveLength(0);
  });
});
