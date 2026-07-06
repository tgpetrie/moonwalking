import { describe, expect, it } from "vitest";
import { deriveDashboardCadence } from "./cadence";

describe("deriveDashboardCadence", () => {
  it("preserves immediate UI publish when cadence is zero", () => {
    const cadence = deriveDashboardCadence({
      VITE_PUBLISH_UI_MS: "0",
    });

    expect(cadence.PUBLISH_UI_MS).toBe(0);
  });

  it("keeps 3m publishing slower than the 1m feed", () => {
    const cadence = deriveDashboardCadence({
      VITE_FAST_1M_MS: "8000",
      VITE_PUBLISH_3M_MS: "2000",
    });

    expect(cadence.FAST_1M_MS).toBe(8000);
    expect(cadence.PUBLISH_3M_MS).toBeGreaterThan(cadence.FAST_1M_MS);
  });

  it("keeps banners slower than the 3m publish cadence", () => {
    const cadence = deriveDashboardCadence({
      VITE_FAST_1M_MS: "8000",
      VITE_PUBLISH_3M_MS: "25000",
      VITE_PUBLISH_BANNER_MS: "10000",
    });

    expect(cadence.PUBLISH_3M_MS).toBe(25000);
    expect(cadence.PUBLISH_BANNER_MS).toBeGreaterThan(cadence.PUBLISH_3M_MS);
  });
});
