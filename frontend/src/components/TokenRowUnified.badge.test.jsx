import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TokenRowUnified } from "./TokenRowUnified.jsx";

/**
 * The badge shows a display label ("Tape confirmed") while its CSS class is
 * built from the underlying status key ("confirmed"). Those two must not be
 * allowed to drift back together: `bh-live-rank--${label.toLowerCase()}` on a
 * label containing a space renders as two classes and silently loses the
 * badge styling. These tests assert the text and the class independently.
 */

const confirmedToken = {
  symbol: "BTC",
  price: 65000,
  live_score: 72,
  live_rank: 1,
  universe_size: 120,
  data_quality: 83,
  observed_inputs: 5,
  expected_inputs: 6,
  live_label: "Strong",
  live_reasons: ["3m +1.80%"],
  live_risks: [],
};

function renderRow(token, side = "gainer") {
  return render(<TokenRowUnified token={token} side={side} rank={1} />);
}

describe("TokenRowUnified live-rank badge", () => {
  it("shows the narrowed 'Tape confirmed' label", () => {
    renderRow(confirmedToken);
    expect(screen.getByText("Tape confirmed")).toBeTruthy();
  });

  it("shows 'Tape confirmed down' for losers while retaining the confirmed class", () => {
    const { container } = renderRow({ ...confirmedToken, live_score: 28 }, "loser");
    expect(screen.getByText("Tape confirmed down")).toBeTruthy();
    expect([...container.querySelector(".bh-live-rank").classList]).toEqual([
      "bh-live-rank",
      "bh-live-rank--confirmed",
    ]);
  });

  it("never shows the bare 'Confirmed' label that collided with popup posture", () => {
    renderRow(confirmedToken);
    expect(screen.queryByText("Confirmed")).toBeNull();
  });

  it("keeps the confirmed tone class intact after the rename", () => {
    const { container } = renderRow(confirmedToken);
    const badge = container.querySelector(".bh-live-rank");
    expect(badge).toBeTruthy();
    expect(badge.classList.contains("bh-live-rank--confirmed")).toBe(true);
  });

  it("builds exactly two classes, so no whitespace leaked into the class name", () => {
    const { container } = renderRow(confirmedToken);
    const badge = container.querySelector(".bh-live-rank");
    expect([...badge.classList]).toEqual(["bh-live-rank", "bh-live-rank--confirmed"]);
  });

  it("leaves unconfirmed rows unchanged in both label and class", () => {
    const { container } = renderRow({ ...confirmedToken, live_score: 58 });
    const badge = container.querySelector(".bh-live-rank");
    expect(screen.getByText("Unconfirmed")).toBeTruthy();
    expect([...badge.classList]).toEqual(["bh-live-rank", "bh-live-rank--unconfirmed"]);
  });

  it("leaves thin rows unchanged in both label and class", () => {
    const { container } = renderRow({ ...confirmedToken, data_quality: 33 });
    const badge = container.querySelector(".bh-live-rank");
    expect(screen.getByText("Thin")).toBeTruthy();
    expect([...badge.classList]).toEqual(["bh-live-rank", "bh-live-rank--thin"]);
  });

  it("describes the badge with the display label in its tooltip", () => {
    const { container } = renderRow(confirmedToken);
    const badge = container.querySelector(".bh-live-rank");
    expect(badge.getAttribute("title")).toMatch(/^Tape confirmed move · live strength #1/);
  });
});
