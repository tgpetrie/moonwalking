const clamp = (n, min, max) => Math.min(max, Math.max(min, n));

const toFinite = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const toRatio01 = (value) => {
  const n = toFinite(value);
  if (n === null) return null;
  if (n > 1 && n <= 100) return clamp(n / 100, 0, 1);
  return clamp(n, 0, 1);
};

const toPercent100 = (value) => {
  const n = toFinite(value);
  if (n === null) return null;
  if (n >= 0 && n <= 1) return clamp(n * 100, 0, 100);
  return clamp(n, 0, 100);
};

const deriveLabelFromIndex = (index) => {
  if (!Number.isFinite(index)) return "Neutral";
  if (index <= 20) return "Fear";
  if (index <= 40) return "Cautious";
  if (index <= 60) return "Neutral";
  if (index <= 80) return "Risk-On";
  return "Euphoria";
};

const deriveBiasFromIndex = (index) => {
  if (!Number.isFinite(index)) return "neutral";
  if (index >= 60) return "up";
  if (index <= 40) return "down";
  return "neutral";
};

const extractRawMarketPressure = (input) => {
  if (!input || typeof input !== "object") return null;

  const candidates = [
    input.market_pressure,
    input.data?.market_pressure,
    input.payload?.market_pressure,
    input.payload?.data?.market_pressure,
    input.meta?.market_pressure,
    input.alertsMeta?.market_pressure,
    input,
  ];

  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== "object") continue;
    if (
      candidate.market_pressure ||
      candidate.data?.market_pressure ||
      candidate.payload?.market_pressure ||
      candidate.payload?.data?.market_pressure
    ) {
      continue;
    }

    const hasSignal =
      toFinite(candidate.index) !== null ||
      toFinite(candidate.heat) !== null ||
      toFinite(candidate.score01) !== null ||
      (candidate.components && typeof candidate.components === "object");

    if (hasSignal) return candidate;
  }

  return null;
};

export function getMarketPressure(input) {
  const raw = extractRawMarketPressure(input);

  if (!raw) {
    return {
      index: 50,
      label: "Neutral",
      score01: 0.5,
      components: {
        breadth: 0,
        impulse_density: 0,
        volume_anomaly: 0,
        vol_regime: 0,
        persistence: 0,
      },
      ts: Math.floor(Date.now() / 1000),
      heat: 50,
      bias: "neutral",
      breadth_up: null,
      breadth_down: null,
      impulse_count: null,
      symbol_count: null,
    };
  }

  const indexFromCanonical = toPercent100(raw.index);
  const indexFromHeat = toPercent100(raw.heat);
  const indexFromScore = toPercent100(raw.score01);
  const index =
    indexFromCanonical ??
    indexFromHeat ??
    indexFromScore ??
    50;

  const score01Raw = toRatio01(raw.score01);
  const score01 = score01Raw ?? clamp(index / 100, 0, 1);

  const label = typeof raw.label === "string" && raw.label.trim()
    ? raw.label.trim()
    : deriveLabelFromIndex(index);

  const components = raw.components && typeof raw.components === "object" ? raw.components : {};

  const breadthRaw =
    toRatio01(components.breadth) ??
    toRatio01(components.breadth_up) ??
    toRatio01(raw.breadth_up) ??
    toRatio01(components.breadth_3m);

  const impulseDensityRaw =
    toRatio01(components.impulse_density) ??
    toRatio01(components.impulseDensity) ??
    (() => {
      const impulseCount = toFinite(raw.impulse_count);
      const symbolCount = toFinite(raw.symbol_count);
      if (impulseCount === null || symbolCount === null || symbolCount <= 0) return null;
      return clamp(impulseCount / symbolCount, 0, 1);
    })();

  const volumeAnomalyRaw =
    toRatio01(components.volume_anomaly) ??
    toRatio01(components.volumeAnomaly);

  const volRegimeRaw =
    toRatio01(components.vol_regime) ??
    toRatio01(components.volRegime) ??
    toRatio01(components.volatility);

  const persistenceRaw = toRatio01(components.persistence);

  const ts = toFinite(raw.ts) ?? Math.floor(Date.now() / 1000);

  const bias = typeof raw.bias === "string" && raw.bias.trim()
    ? raw.bias.trim().toLowerCase()
    : deriveBiasFromIndex(index);

  const breadthUp = toRatio01(raw.breadth_up);
  const breadthDown = toRatio01(raw.breadth_down);

  return {
    index,
    label,
    score01,
    components: {
      breadth: breadthRaw ?? 0,
      impulse_density: impulseDensityRaw ?? 0,
      volume_anomaly: volumeAnomalyRaw ?? 0,
      vol_regime: volRegimeRaw ?? 0,
      persistence: persistenceRaw ?? 0,
    },
    ts,
    heat: index,
    bias,
    breadth_up: breadthUp,
    breadth_down: breadthDown,
    impulse_count: toFinite(raw.impulse_count),
    symbol_count: toFinite(raw.symbol_count),
  };
}

export default getMarketPressure;
