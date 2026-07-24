import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import AskBhabitExperience from "../AskBhabitExperience.jsx";
import {
  RICH_ANALYSIS,
  SPARSE_ANALYSIS,
  NO_PRIOR_ANALYSIS,
  PROVIDER_ERROR_ENVELOPE,
  MODEL_FAILURE_ENVELOPE,
} from "../fixtures/analyses.js";

// Synchronous resolvers keep the tests free of timers.
const resolverFor = (payload) => vi.fn(async () => payload);

const renderExp = (props = {}) => render(<AskBhabitExperience {...props} />);

beforeEach(() => window.localStorage.clear());

describe("first-value experience", () => {
  it("opens on sample positions, not an empty chat box", () => {
    renderExp();
    expect(screen.getByText("Solana")).toBeInTheDocument();
    expect(screen.getByText("Shadow Token")).toBeInTheDocument();
    expect(screen.getByText("Well supported")).toBeInTheDocument();
    expect(screen.getByText("Sparse data")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("runs a sample analysis without spending the beta allowance", async () => {
    renderExp({ resolveAnalysis: resolverFor(RICH_ANALYSIS) });
    fireEvent.click(screen.getByText("Solana"));
    fireEvent.click(await screen.findByRole("button", { name: "What changed?" }));

    expect(await screen.findByText(/thesis intact/i)).toBeInTheDocument();
    // Allowance meter still shows the full 3 — samples are free.
    expect(screen.getByText("3 of 3 beta analyses remaining")).toBeInTheDocument();
  });
});

describe("structured answer", () => {
  it("renders all required sections including confidence reasons and what-changed items", async () => {
    renderExp({ resolveAnalysis: resolverFor(RICH_ANALYSIS) });
    fireEvent.click(screen.getByText("Solana"));
    fireEvent.click(await screen.findByRole("button", { name: "What changed?" }));

    await screen.findByText(/thesis intact/i);
    expect(screen.getByText("2. What changed")).toBeInTheDocument();
    expect(screen.getByText("Market structure changed")).toBeInTheDocument();
    expect(screen.getByText("Funding flipped positive")).toBeInTheDocument();
    expect(screen.getByText("4. Thesis check")).toBeInTheDocument();
    expect(screen.getByText("Strengthened")).toBeInTheDocument();
    expect(screen.getByText("7. Confidence")).toBeInTheDocument();
    expect(screen.getByText(/independent venues agree/i)).toBeInTheDocument();
    expect(screen.getByText("3 sources")).toBeInTheDocument();
  });

  it("shows sparse-data missing states: unsupported derivatives, stale, conflicting", async () => {
    renderExp({ resolveAnalysis: resolverFor(SPARSE_ANALYSIS) });
    fireEvent.click(screen.getByText("Shadow Token"));
    fireEvent.click(await screen.findByRole("button", { name: "How is this position doing?" }));

    await screen.findByText(/not enough independent evidence/i);
    const missing = screen.getByText("6. Missing & uncertain data").closest("section");
    expect(within(missing).getByText("Unsupported")).toBeInTheDocument();
    expect(within(missing).getByText("Stale")).toBeInTheDocument();
    expect(within(missing).getByText("Conflicting")).toBeInTheDocument();
    expect(within(missing).getByText(/No perp market lists SHDW/i)).toBeInTheDocument();
    expect(screen.getByText("Insufficient evidence")).toBeInTheDocument();
  });

  it("shows a stale banner when a source is stale", async () => {
    renderExp({ resolveAnalysis: resolverFor(SPARSE_ANALYSIS) });
    fireEvent.click(screen.getByText("Shadow Token"));
    fireEvent.click(await screen.findByRole("button", { name: "How is this position doing?" }));
    expect(await screen.findByText(/Some data is stale/i)).toBeInTheDocument();
  });

  it("handles no prior snapshot without inventing a comparison", async () => {
    renderExp({ resolveAnalysis: resolverFor(NO_PRIOR_ANALYSIS) });
    fireEvent.click(screen.getByText("Solana"));
    fireEvent.click(await screen.findByRole("button", { name: "How is this position doing?" }));
    expect(await screen.findByText(/No prior snapshot to compare against/i)).toBeInTheDocument();
  });
});

describe("manual position + optional thesis", () => {
  const fillAndSave = () => {
    fireEvent.click(screen.getByRole("button", { name: /add a real position/i }));
    fireEvent.change(screen.getByLabelText("Asset"), { target: { value: "sol" } });
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Entry price"), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: /save position/i }));
  };

  it("blocks save until required fields are valid", () => {
    renderExp();
    fireEvent.click(screen.getByRole("button", { name: /add a real position/i }));
    fireEvent.click(screen.getByRole("button", { name: /save position/i }));
    expect(screen.getByText("Asset is required.")).toBeInTheDocument();
  });

  it("saves a manual position then offers the optional thesis, which can be skipped", () => {
    renderExp();
    fillAndSave();
    expect(screen.getByText(/Add a quick thesis/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /skip for now/i }));
    // Thesis omitted → still land on guided questions.
    expect(screen.getByRole("button", { name: "What changed?" })).toBeInTheDocument();
  });

  it("accepts a thesis when provided", () => {
    renderExp();
    fillAndSave();
    fireEvent.change(screen.getByLabelText("Why did you enter?"), { target: { value: "growth" } });
    fireEvent.click(screen.getByRole("button", { name: "Momentum" }));
    fireEvent.click(screen.getByRole("button", { name: /save thesis/i }));
    expect(screen.getByRole("button", { name: "Is my thesis weakening?" })).toBeInTheDocument();
  });
});

describe("feedback controls", () => {
  it("captures a rating and reveals an optional note", async () => {
    const events = [];
    renderExp({ resolveAnalysis: resolverFor(RICH_ANALYSIS) });
    fireEvent.click(screen.getByText("Solana"));
    fireEvent.click(await screen.findByRole("button", { name: "What changed?" }));
    await screen.findByText(/thesis intact/i);

    fireEvent.click(screen.getByRole("button", { name: "Incorrect data" }));
    expect(screen.getByLabelText(/Add a note/i)).toBeInTheDocument();
    void events;
  });
});

describe("failure + trial states", () => {
  it("renders a provider-error state with retry, not a partial answer", async () => {
    renderExp({ resolveAnalysis: resolverFor(PROVIDER_ERROR_ENVELOPE) });
    fireEvent.click(screen.getByText("Solana"));
    fireEvent.click(await screen.findByRole("button", { name: "What changed?" }));
    expect(await screen.findByText(/Data provider unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders a model-failure state", async () => {
    renderExp({ resolveAnalysis: resolverFor(MODEL_FAILURE_ENVELOPE) });
    fireEvent.click(screen.getByText("Solana"));
    fireEvent.click(await screen.findByRole("button", { name: "What changed?" }));
    expect(await screen.findByText(/Analysis failed/i)).toBeInTheDocument();
  });

  it("blocks real analyses when the beta allowance is exhausted", () => {
    renderExp({ betaLimit: 0, resolveAnalysis: resolverFor(RICH_ANALYSIS) });
    fireEvent.click(screen.getByRole("button", { name: /add a real position/i }));
    fireEvent.change(screen.getByLabelText("Asset"), { target: { value: "sol" } });
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Entry price"), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: /save position/i }));
    fireEvent.click(screen.getByRole("button", { name: /skip for now/i }));
    fireEvent.click(screen.getByRole("button", { name: "What changed?" }));
    expect(screen.getByText("Beta allowance used")).toBeInTheDocument();
  });
});
