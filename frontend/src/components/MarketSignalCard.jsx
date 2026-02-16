import { useMemo } from 'react';
import { useData } from '../context/DataContext';

/**
 * Compute market signal from existing tape data.
 * No external APIs, no vibes, just actionable truth.
 */
function computeMarketSignal(data, activeAlerts = [], alertsRecent = []) {
  // Extract existing data slices
  const gainers1m = Array.isArray(data?.gainers_1m) ? data.gainers_1m : [];
  const gainers3m = Array.isArray(data?.gainers_3m) ? data.gainers_3m : [];
  const losers3m = Array.isArray(data?.losers_3m) ? data.losers_3m : [];
  const banner1hPrice = Array.isArray(data?.banner_1h_price) ? data.banner_1h_price : [];

  // A) Direction score (-100 to +100): 3m breadth weighted by magnitude
  let directionScore = 0;
  const allCoins3m = [...gainers3m, ...losers3m];

  if (allCoins3m.length > 0) {
    const gainersSum = gainers3m.reduce((sum, c) => {
      const pct = Number(c?.pct_3m ?? c?.pct ?? 0);
      return sum + Math.abs(pct);
    }, 0);

    const losersSum = losers3m.reduce((sum, c) => {
      const pct = Number(c?.pct_3m ?? c?.pct ?? 0);
      return sum + Math.abs(pct);
    }, 0);

    const totalMagnitude = gainersSum + losersSum;
    if (totalMagnitude > 0) {
      directionScore = ((gainersSum - losersSum) / totalMagnitude) * 100;
    }
  }

  // B) Agreement score (0-100): do 1h and 3m agree? Do alerts match?
  let agreementScore = 0;

  // 1h vs 3m alignment
  const avg1h = banner1hPrice.reduce((sum, c) => sum + Number(c?.pct_1h ?? c?.pct ?? 0), 0) / Math.max(1, banner1hPrice.length);
  const avg3m = directionScore;

  const sign1h = avg1h > 0 ? 1 : avg1h < 0 ? -1 : 0;
  const sign3m = avg3m > 0 ? 1 : avg3m < 0 ? -1 : 0;

  const timeframeAlign = sign1h === sign3m && sign1h !== 0 ? 50 : 0;

  // Alert alignment: do alert types match direction?
  const allAlerts = [...activeAlerts, ...alertsRecent].slice(0, 20);
  const upAlerts = allAlerts.filter(a => {
    const type = String(a?.type_key || a?.type || '').toLowerCase();
    return type.includes('moonshot') || type.includes('breakout') || type.includes('coin_fomo');
  }).length;

  const downAlerts = allAlerts.filter(a => {
    const type = String(a?.type_key || a?.type || '').toLowerCase();
    return type.includes('crater') || type.includes('dump') || type.includes('breakdown');
  }).length;

  const totalSignalAlerts = upAlerts + downAlerts;
  const alertAlign = totalSignalAlerts > 0
    ? (directionScore > 0 && upAlerts > downAlerts) || (directionScore < 0 && downAlerts > upAlerts)
      ? 40
      : 0
    : 10; // No strong directional alerts = slight penalty

  agreementScore = Math.min(100, timeframeAlign + alertAlign + 10); // Base 10 for stability

  // C) Regime classification
  const absDirection = Math.abs(directionScore);
  const volatility = gainers1m.length + losers3m.length; // Proxy for market activity

  let regime = 'Neutral';
  if (absDirection < 20 && volatility < 15) {
    regime = 'Calm';
  } else if (absDirection < 25 && agreementScore < 40) {
    regime = 'Chop';
  } else if (directionScore > 25 && agreementScore >= 50) {
    regime = 'Risk-On';
  } else if (directionScore < -25 && agreementScore >= 50) {
    regime = 'Risk-Off';
  }

  // D) Action sentence mapping
  let actionLine = 'No high-conviction setup yet: wait for alignment.';

  if (regime === 'Risk-On' && agreementScore >= 60) {
    actionLine = 'Trade with trend; prioritize breakouts on pullbacks.';
  } else if (regime === 'Risk-Off' && agreementScore >= 60) {
    actionLine = 'Protect capital; downside impulses are dominant.';
  } else if (regime === 'Chop') {
    actionLine = 'Avoid chasing; wait for clean directional confirmation.';
  } else if (regime === 'Calm') {
    actionLine = 'Low edge environment: size down or wait for setups.';
  } else if (agreementScore < 40) {
    actionLine = 'Mixed signals: reduce size until clarity emerges.';
  }

  return {
    regime,
    conviction: Math.round(agreementScore),
    direction: Math.round(directionScore),
    actionLine,
  };
}

export default function MarketSignalCard() {
  const { data, activeAlerts = [], alertsRecent = [] } = useData() || {};

  const signal = useMemo(() => {
    return computeMarketSignal(data, activeAlerts, alertsRecent);
  }, [data, activeAlerts, alertsRecent]);

  const regimeTone =
    signal.regime === 'Risk-On' ? 'positive' :
    signal.regime === 'Risk-Off' ? 'negative' :
    'neutral';

  return (
    <div className="mw-market-signal">
      <div className="section-header">
        <h3>Market Signal</h3>
        <p className="section-desc">Tape-derived conviction and action for the current market regime.</p>
      </div>

      <div className="mw-signal-grid">
        <div className="mw-signal-card">
          <span className="mw-signal-label">Regime</span>
          <span className={`mw-signal-value ${regimeTone}`}>{signal.regime}</span>
        </div>

        <div className="mw-signal-card">
          <span className="mw-signal-label">Conviction</span>
          <span className={`mw-signal-value ${signal.conviction >= 60 ? 'positive' : signal.conviction <= 40 ? 'negative' : 'neutral'}`}>
            {signal.conviction}
          </span>
          <span className="mw-signal-sub">0–100 scale</span>
        </div>
      </div>

      <div className="mw-action-panel">
        <span className="mw-action-label">Do This Now</span>
        <p className="mw-action-line">{signal.actionLine}</p>
      </div>
    </div>
  );
}
