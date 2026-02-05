import assert from "node:assert";
import test from "node:test";
import { pearsonCorrelation } from "../stats.js";

test("pearsonCorrelation handles perfect positive correlation", () => {
  const xs = [1, 2, 3, 4, 5];
  const ys = [2, 4, 6, 8, 10];
  const r = pearsonCorrelation(xs, ys);
  assert.ok(r !== null);
  assert.ok(r > 0.99);
});

test("pearsonCorrelation returns null for invalid input", () => {
  assert.strictEqual(pearsonCorrelation([1], [2, 3]), null);
  assert.strictEqual(pearsonCorrelation([], []), null);
});
