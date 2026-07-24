import { afterEach, describe, expect, it, vi } from "vitest";
import { AskBhabitClientError, resolveLiveAnalysis } from "../askBhabitClient.js";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("resolveLiveAnalysis", () => {
  it("keeps network failure distinct from backend validation failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("connection refused");
    }));

    await expect(
      resolveLiveAnalysis({
        position: { asset: "SOL", quantity: 1, entryPrice: 10, costBasis: 10 },
        question: { id: "how_doing" },
        isSample: false,
      })
    ).rejects.toMatchObject({ kind: "network_failure" });
  });

  it("surfaces backend validation envelopes without faking success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        json: async () => ({
          success: false,
          error: { code: "position_required", message: "Create a manual position first." },
        }),
      }))
    );

    await expect(
      resolveLiveAnalysis({
        position: { asset: "SOL", quantity: 1, entryPrice: 10, costBasis: 10 },
        question: { id: "how_doing" },
        isSample: false,
      })
    ).rejects.toBeInstanceOf(AskBhabitClientError);
  });
});
