import { describe, expect, it, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useBetaAllowance } from "../useBetaAllowance.js";

describe("useBetaAllowance", () => {
  beforeEach(() => window.localStorage.clear());

  it("starts with the full allowance and a friendly label", () => {
    const { result } = renderHook(() => useBetaAllowance(3));
    expect(result.current.remaining).toBe(3);
    expect(result.current.exhausted).toBe(false);
    expect(result.current.label).toBe("3 of 3 beta analyses remaining");
  });

  it("consumes down to exhaustion and switches the message", () => {
    const { result } = renderHook(() => useBetaAllowance(2));
    act(() => result.current.consume());
    act(() => result.current.consume());
    expect(result.current.remaining).toBe(0);
    expect(result.current.exhausted).toBe(true);
    expect(result.current.label).toMatch(/allowance has been used/i);
  });

  it("persists usage across remounts via localStorage", () => {
    const first = renderHook(() => useBetaAllowance(3));
    act(() => first.result.current.consume());
    const second = renderHook(() => useBetaAllowance(3));
    expect(second.result.current.remaining).toBe(2);
  });
});
