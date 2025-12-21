import React, { useEffect, useMemo, useState } from "react";

const clamp = (n, a, b) => Math.max(a, Math.min(b, n));

function setVar(name, value) {
  document.documentElement.style.setProperty(name, String(value));
}

export default function StyleTuner({ enabled }) {
  const isDev = import.meta?.env?.DEV;
  const showTuner = useMemo(() => {
    if (!isDev) return false;
    if (typeof window === "undefined") return false;
    return new URLSearchParams(window.location.search).has("tune");
  }, [isDev]);

  const on = enabled ?? showTuner;

  const defaults = useMemo(
    () => ({
      glassContrast: 3.35,
      rabbitOpacity: 0.010,
      goldCore: 0.14,
      violetCore: 0.16,
    }),
    []
  );

  const [v, setV] = useState(defaults);

  useEffect(() => {
    if (!on) return;
    setVar("--bh-glass-contrast", v.glassContrast);
    setVar("--bh-rabbit-opacity", v.rabbitOpacity);
    setVar("--bh-g-core1", v.goldCore);
    setVar("--bh-l-core1", v.violetCore);
  }, [on, v]);

  if (!on) return null;

  const Row = ({ label, keyName, min, max, step }) => (
    <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 64px", gap: 10, alignItems: "center" }}>
      <div style={{ color: "rgba(255,255,255,0.78)", fontSize: 12 }}>{label}</div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={v[keyName]}
        onChange={(e) => setV(s => ({ ...s, [keyName]: clamp(parseFloat(e.target.value), min, max) }))}
      />
      <div style={{ color: "rgba(255,255,255,0.6)", fontSize: 12, textAlign: "right" }}>
        {Number(v[keyName]).toFixed(3)}
      </div>
    </div>
  );

  return (
    <div className="style-tuner">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
        <div style={{ fontSize: 13, letterSpacing: 0.4, opacity: 0.9 }}>Style Tuner</div>
        <button
          onClick={() => setV(defaults)}
          style={{
            fontSize: 12,
            color: "rgba(255,255,255,0.75)",
            background: "transparent",
            border: "1px solid rgba(255,255,255,0.14)",
            padding: "4px 8px",
            borderRadius: 10,
            cursor: "pointer"
          }}
        >
          Reset
        </button>
      </div>

      <div style={{ display: "grid", gap: 10 }}>
        <Row label="Glass contrast" keyName="glassContrast" min={2.0} max={5.0} step={0.05} />
        <Row label="Rabbit opacity" keyName="rabbitOpacity" min={0.002} max={0.030} step={0.001} />
        <Row label="Glow core (gold)" keyName="goldCore" min={0.06} max={0.30} step={0.01} />
        <Row label="Glow core (purple)" keyName="violetCore" min={0.06} max={0.35} step={0.01} />
      </div>
    </div>
  );
}
