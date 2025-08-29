const { computePct } = (() => {
  function computePct(past, now) {
    if (!Number.isFinite(past) || past === 0) return null;
    return ((now - past) / past) * 100;
  }
  return { computePct };
})();

function assertEqual(a, b, eps = 1e-9) {
  if (a === null && b === null) return true;
  if (a === null || b === null) throw new Error(`Assertion failed: ${a} !== ${b}`);
  if (Math.abs(a - b) > eps) throw new Error(`Assertion failed: ${a} !== ${b}`);
  return true;
}

console.log('running gainers pct tests...');
try {
  assertEqual(computePct(100, 110), 10);
  assertEqual(computePct(50, 75), 50);
  assertEqual(computePct(1, 1.01), 1);
  assertEqual(computePct(0, 1), null);
  assertEqual(computePct(NaN, 1), null);
  console.log('all tests passed');
} catch (e) {
  console.error(e.message);
  process.exit(1);
}
