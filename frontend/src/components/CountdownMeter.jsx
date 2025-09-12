import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';

// Horizontal purple bar that shrinks from 100% to 0% over durationMs
export default function CountdownMeter({ durationMs = 30000, running = true, keySeed }) {
  const [pct, setPct] = useState(100);

  useEffect(() => {
    if (!running) return;
    const start = Date.now();
    let raf;
    const tick = () => {
      const elapsed = Date.now() - start;
      const remaining = Math.max(0, durationMs - elapsed);
      const nextPct = Math.max(0, Math.min(100, Math.round((remaining / durationMs) * 100)));
      setPct(nextPct);
      if (remaining > 0) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [durationMs, running, keySeed]);

  return (
    <div className="w-40 h-2 bg-white/10 rounded-full overflow-hidden" aria-label="Countdown">
      <div
        className="h-full bg-purple-500 transition-[width] duration-150 ease-linear"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

CountdownMeter.propTypes = {
  durationMs: PropTypes.number,
  running: PropTypes.bool,
  keySeed: PropTypes.any,
};
