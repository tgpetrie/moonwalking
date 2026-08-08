import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import QuickAlertBuilder from "./QuickAlertBuilder.jsx";

const setup = (onCreate = vi.fn()) => {
  const utils = render(<QuickAlertBuilder onCreate={onCreate} />);
  return { onCreate, ...utils };
};

describe("QuickAlertBuilder", () => {
  it("reads as a natural-language sentence", () => {
    const { container } = setup();
    expect(screen.getByText("Alert me when")).toBeInTheDocument();
    expect(screen.getByText("during")).toBeInTheDocument();
    // Percent flow shows plain-language direction and window options.
    expect(screen.getByLabelText("Direction")).toHaveValue("either");
    expect(container.textContent).toContain("a rolling 24-hour period");
  });

  it("offers only 1h, 4h and 24h windows — never 7d", () => {
    setup();
    const windowSelect = screen.getByLabelText("Time window");
    const values = [...windowSelect.querySelectorAll("option")].map((o) => o.value);
    expect(values).toEqual(["1h", "4h", "24h"]);
    expect(values).not.toContain("7d");
  });

  it("has no 7d anywhere in the rendered DOM", () => {
    const { container } = setup();
    expect(container.innerHTML).not.toMatch(/7d|7-day|rolling 7/i);
  });

  it("hides the time window for a price target", () => {
    setup();
    fireEvent.change(screen.getByLabelText("What to watch"), {
      target: { value: "price_cross" },
    });
    expect(screen.queryByLabelText("Time window")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Price")).toBeInTheDocument();
  });

  it("uses plain wording, never trader jargon", () => {
    const { container } = setup();
    fireEvent.change(screen.getByLabelText("What to watch"), {
      target: { value: "price_cross" },
    });
    const text = container.textContent.toLowerCase();
    expect(text).toContain("goes above");
    for (const jargon of ["crossing down", "bar close", "invalidation", "standard deviation"]) {
      expect(text).not.toContain(jargon);
    }
  });

  it("never shows buy/sell/hold advice", () => {
    const { container } = setup();
    const text = container.textContent.toLowerCase();
    for (const word of [" buy ", " sell ", " hold ", "stop loss", "take profit"]) {
      expect(text).not.toContain(word);
    }
  });

  it("resets direction when the trigger type changes", () => {
    setup();
    // 'either' is valid for percent_move but not for price_cross.
    expect(screen.getByLabelText("Direction")).toHaveValue("either");
    fireEvent.change(screen.getByLabelText("What to watch"), {
      target: { value: "price_cross" },
    });
    expect(screen.getByLabelText("Direction")).toHaveValue("above");
  });

  it("blocks submission without a coin", async () => {
    const { onCreate } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Create alert" }));
    expect(await screen.findByText("Choose a coin.")).toBeInTheDocument();
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("blocks a non-positive threshold", async () => {
    const { onCreate } = setup();
    fireEvent.change(screen.getByLabelText("Coin"), { target: { value: "BTC" } });
    fireEvent.change(screen.getByLabelText("Percentage"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Create alert" }));
    expect(await screen.findByText("Enter a percentage above zero.")).toBeInTheDocument();
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("submits a well-formed percent_move payload", async () => {
    const onCreate = vi.fn().mockResolvedValue({ id: "rule_1" });
    setup(onCreate);
    fireEvent.change(screen.getByLabelText("Coin"), { target: { value: "btc" } });
    fireEvent.change(screen.getByLabelText("Percentage"), { target: { value: "7" } });
    fireEvent.change(screen.getByLabelText("Time window"), { target: { value: "4h" } });
    fireEvent.click(screen.getByRole("button", { name: "Create alert" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1));
    expect(onCreate).toHaveBeenCalledWith({
      symbol: "BTC",
      trigger_type: "percent_move",
      params: { direction: "either", threshold: 7, window: "4h" },
      repeat_mode: "once",
    });
  });

  it("submits a well-formed price_cross payload without a window", async () => {
    const onCreate = vi.fn().mockResolvedValue({ id: "rule_2" });
    setup(onCreate);
    fireEvent.change(screen.getByLabelText("What to watch"), {
      target: { value: "price_cross" },
    });
    fireEvent.change(screen.getByLabelText("Coin"), { target: { value: "ETH" } });
    fireEvent.change(screen.getByLabelText("Price"), { target: { value: "4000" } });
    fireEvent.click(screen.getByRole("button", { name: "Create alert" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1));
    const payload = onCreate.mock.calls[0][0];
    expect(payload.trigger_type).toBe("price_cross");
    expect(payload.params).toEqual({ direction: "above", threshold: 4000 });
    expect(payload.params).not.toHaveProperty("window");
  });

  it("surfaces the server's own validation message", async () => {
    const onCreate = vi
      .fn()
      .mockRejectedValue(new Error("That target is already at or below the current price ($100.00)."));
    setup(onCreate);
    fireEvent.change(screen.getByLabelText("Coin"), { target: { value: "BTC" } });
    fireEvent.click(screen.getByRole("button", { name: "Create alert" }));

    expect(
      await screen.findByText(/already at or below the current price/)
    ).toBeInTheDocument();
  });

  it("keeps advanced options collapsed by default", () => {
    setup();
    expect(screen.queryByText("Notify once")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Customize" }));
    expect(screen.getByText("Notify once")).toBeInTheDocument();
  });
});
