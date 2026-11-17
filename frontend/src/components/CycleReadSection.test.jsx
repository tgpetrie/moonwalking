import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CycleReadSection, { CycleReplayStrip } from "./CycleReadSection.jsx";

const backtest = (extra = {}) => ({
  available: true,
  hodl_final_coins: 100,
  compounded_final_coins: 191.2345,
  extra_coins_pct: 91.2345,
  strategy_final_coin_equivalent: 191.2345,
  max_drawdown_hodl_pct: 80.1,
  max_drawdown_strategy_pct: 52.34,
  drawdown_reduction_pct: 27.76,
  completed_trim_reload_cycles: 1,
  ended_stopped_out: false,
  ...extra,
});

describe("CycleReplayStrip", () => {
  it("shows compounded vs HODL, the coin-equivalent stack, drawdown reduction and cycles", () => {
    render(<CycleReplayStrip backtest={backtest()} />);
    const strip = screen.getByTestId("cycle-replay");
    expect(within(strip).getByText("Historical cycle replay")).toBeInTheDocument();
    const coins = screen.getByTestId("cycle-replay-coins");
    expect(coins).toHaveTextContent("Compounded vs HODL");
    expect(coins).toHaveTextContent("191.23 / 100");
    expect(coins).toHaveTextContent("+91.2% coins");
    expect(screen.getByTestId("cycle-replay-equivalent")).toHaveTextContent("191.23");
    const drawdown = screen.getByTestId("cycle-replay-drawdown");
    expect(drawdown).toHaveTextContent("−27.8 pts");
    expect(drawdown).toHaveTextContent("52.3% vs 80.1% HODL");
    expect(screen.getByTestId("cycle-replay-cycles")).toHaveTextContent("1");
    expect(strip).toHaveTextContent("no added cash");
    expect(strip).not.toHaveTextContent("stopped out");
  });

  it("reads a losing or stopped-out replay honestly", () => {
    render(<CycleReplayStrip backtest={backtest({
      compounded_final_coins: 0,
      extra_coins_pct: -100,
      strategy_final_coin_equivalent: 140,
      drawdown_reduction_pct: -3.5,
      completed_trim_reload_cycles: 0,
      ended_stopped_out: true,
    })} />);
    expect(screen.getByTestId("cycle-replay-coins")).toHaveTextContent("-100.0% coins");
    expect(screen.getByTestId("cycle-replay-drawdown")).toHaveTextContent("+3.5 pts");
    expect(screen.getByTestId("cycle-replay")).toHaveTextContent("It ends stopped out in USDC.");
  });

  it("renders nothing without an available replay", () => {
    const { container, rerender } = render(<CycleReplayStrip backtest={undefined} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<CycleReplayStrip backtest={{ available: false, reason: "replay_failed" }} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("CycleReadSection", () => {
  it("places the replay strip inside the cycle read when the context carries one", () => {
    const { rerender } = render(<CycleReadSection context={{ available: true, backtest: backtest() }} />);
    expect(within(screen.getByTestId("cycle-read")).getByTestId("cycle-replay")).toBeInTheDocument();
    rerender(<CycleReadSection context={{ available: true }} />);
    expect(screen.queryByTestId("cycle-replay")).not.toBeInTheDocument();
  });
});
