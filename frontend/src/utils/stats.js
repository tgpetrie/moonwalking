export function pearsonCorrelation(xs, ys) {
  if (!xs?.length || xs.length !== ys?.length) return null;
  const n = xs.length;
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;

  let num = 0,
    dx = 0,
    dy = 0;
  for (let i = 0; i < n; i++) {
    const vx = xs[i] - mx;
    const vy = ys[i] - my;
    num += vx * vy;
    dx += vx * vx;
    dy += vy * vy;
  }
  const den = Math.sqrt(dx * dy);
  if (!den) return null;
  return num / den;
}

export function rollingDelta(series, key) {
  if (!Array.isArray(series) || series.length < 2) return [];
  const out = [];
  for (let i = 1; i < series.length; i++) {
    const prev = Number(series[i - 1][key]);
    const curr = Number(series[i][key]);
    if (Number.isFinite(prev) && Number.isFinite(curr)) {
      out.push(curr - prev);
    }
  }
  return out;
}
