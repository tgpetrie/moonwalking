import { expect, test } from "vitest";
import { pearsonCorrelation } from "../stats.js";

test("pearsonCorrelation handles perfect positive correlation", () => {
  const xs = [1, 2, 3, 4, 5];
  const ys = [2, 4, 6, 8, 10];
  const r = pearsonCorrelation(xs, ys);
  expect(r).not.toBeNull();
  expect(r).toBeGreaterThan(0.99);
});

test("pearsonCorrelation returns null for invalid input", () => {
  expect(pearsonCorrelation([1], [2, 3])).toBeNull();
  expect(pearsonCorrelation([], [])).toBeNull();
});
