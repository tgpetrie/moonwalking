import React, { useEffect, useState } from 'react';

const positive = (value) => typeof value === 'number' && Number.isFinite(value) && value > 0;
const priceText = (value) => positive(value)
  ? `$${value.toLocaleString(undefined, { maximumSignificantDigits: 8 })}` : 'Unavailable';
const timeText = (value) => positive(value)
  ? new Date(value * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Unavailable';

export default function RiskLevelsChart({ plan }) {
  const [selected, setSelected] = useState('stop');
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(timer);
  }, []);
  const chart = plan.chart;
  const stop = plan.stop || {};
  const structure = plan.market_structure || {};
  const profit = plan.profit || {};
  const bars = (chart?.candles || []).filter((c) => Array.isArray(c) && c.length >= 6
    && c.every(Number.isFinite) && c[0] >= 0 && c[1] > 0 && c[5] >= 0
    && c[1] <= Math.min(c[3], c[4]) && Math.max(c[3], c[4]) <= c[2])
    .sort((a, b) => a[0] - b[0]);
  if (bars.length < 3 || !positive(plan.current_price)) {
    return <section className="risk-chart risk-levels-empty">Price chart unavailable. Candle history is required to draw the suggested levels.</section>;
  }

  const stale = (positive(plan.price_as_of) && now / 1000 - plan.price_as_of > 120)
    || (positive(chart.last_close_at) && now / 1000 - chart.last_close_at > chart.granularity_seconds * 2);
  const levels = [
    { id: 'resistance', label: positive(profit.first_trim_price) ? 'Resistance / first trim' : 'Observed resistance', price: structure.resistance,
      color: '#b9a0ff', why: profit.why || 'The highest traded price in the measured candle window. A possible area to consider trimming if price reaches it; it is not a confirmed ceiling.' },
    { id: 'current', label: 'Current quote', price: plan.current_price, color: '#e6edf5',
      why: `Latest sampled quote as of ${timeText(plan.price_as_of)}. The final completed candle can close at a different price.` },
    { id: 'support', label: 'Support reference', price: stop.invalidation_price, color: '#5fdbad',
      why: (stop.why || [])[0] || 'The structural reference used by this plan. A break below it weakens the setup.' },
    { id: 'stop', label: 'Suggested stop trigger', price: stop.trigger_price, color: '#ffbc66',
      why: (stop.why || []).join(' ') || 'The suggested activation price for a protective sell stop-limit, with room below the support reference for normal price movement.' },
    { id: 'limit', label: 'Suggested sell limit', price: stop.limit_price, color: '#ff829a',
      why: 'After the stop triggers, this is the lowest acceptable sell price before fees. It sits below the trigger to allow some price movement while the order fills. A fast drop through it can leave the order unfilled.' },
  ].filter((level) => positive(level.price));
  const active = levels.find((level) => level.id === selected) || levels[0];
  const zone = plan.support_zone || {};
  const zoneValid = positive(zone.low) && positive(zone.high) && zone.high >= zone.low;
  const prices = [...bars.flatMap((c) => [c[1], c[2]]), ...levels.map((l) => l.price),
    ...(zoneValid ? [zone.low, zone.high] : [])];
  const low = Math.min(...prices);
  const high = Math.max(...prices);
  const padding = Math.max((high - low) * 0.12, high * 0.001);
  const floor = Math.max(0, low - padding);
  const ceiling = high + padding;
  const y = (price) => 24 + (ceiling - price) / (ceiling - floor) * 290;
  const firstTime = bars[0][0];
  const lastTime = bars[bars.length - 1][0];
  const x = (time) => 22 + (time - firstTime) / Math.max(lastTime - firstTime, 1) * 534;
  const candleWidth = Math.max(1, Math.min(8, 380 / bars.length));
  // Separate nearby labels without moving the actual price lines.
  const positioned = levels.map((level) => ({ ...level, lineY: y(level.price) })).sort((a, b) => a.lineY - b.lineY);
  positioned.forEach((level, i) => { level.labelY = Math.max(level.lineY, i ? positioned[i - 1].labelY + 38 : 26); });
  const overflow = Math.max(0, positioned[positioned.length - 1].labelY - 312);
  positioned.forEach((level) => { level.labelY -= overflow; });
  const volumeMax = Math.max(...bars.map((c) => c[5]), 1);

  return (
    <section className="risk-chart" aria-label="Stop-limit chart and explanations">
      <header className="risk-chart__header">
        <div><h3>Your levels on the chart</h3><p>{chart.product_id || plan.product_id} · {chart.granularity_seconds / 3600}h candles · {bars.length} completed candles</p></div>
        <span className="risk-chart__badge">{stale ? 'Stale snapshot · refresh levels' : 'Suggested levels'}</span>
      </header>
      <p className="risk-chart__hint">Select a labeled line or a level below to see why it is there. Prices are in {String(chart.product_id || plan.product_id || 'USD').split('-').pop()}.</p>
      <div className="risk-chart__scroll" tabIndex={0} role="region" aria-label="Scrollable price chart">
        <svg viewBox="0 0 820 416" className="risk-chart__svg" role="group" aria-label="Candlestick chart with suggested stop and limit prices">
          <title>Completed price candles with support, resistance, stop trigger and sell limit</title>
          {[0, 1, 2, 3, 4].map((i) => <line key={i} x1="16" x2="580" y1={24 + i * 72.5} y2={24 + i * 72.5} stroke="#ffffff0c" />)}
          {zoneValid && <rect x="16" y={y(zone.high)} width="564" height={Math.max(1, y(zone.low) - y(zone.high))} fill="#5fdbad" opacity="0.09"><title>Support watch zone</title></rect>}
          {positive(stop.trigger_price) && positive(stop.limit_price) && stop.trigger_price > stop.limit_price && <rect x="16" y={y(stop.trigger_price)} width="564" height={Math.max(1, y(stop.limit_price) - y(stop.trigger_price))} fill="#ff829a" opacity="0.12"><title>Stop-limit execution band</title></rect>}
          {bars.map((c, i) => {
            const color = c[4] >= c[3] ? '#5fdbad' : '#ff829a';
            return <g key={`${c[0]}-${i}`}>
              <title>{timeText(c[0])} · Open {priceText(c[3])} · High {priceText(c[2])} · Low {priceText(c[1])} · Close {priceText(c[4])}</title>
              <line x1={x(c[0])} x2={x(c[0])} y1={y(c[2])} y2={y(c[1])} stroke={color} />
              <rect x={x(c[0]) - candleWidth / 2} y={y(Math.max(c[3], c[4]))} width={candleWidth} height={Math.max(1, Math.abs(y(c[3]) - y(c[4])))} fill={color} />
              <rect x={x(c[0]) - candleWidth / 2} y={378 - c[5] / volumeMax * 35} width={candleWidth} height={c[5] / volumeMax * 35} fill={color} opacity="0.35" />
            </g>;
          })}
          {positioned.map((level) => <g key={level.id} role="button" tabIndex={0}
            aria-label={`Explain ${level.label.toLowerCase()} at ${priceText(level.price)}`} aria-pressed={active.id === level.id}
            className="risk-chart__line" onClick={() => setSelected(level.id)}
            onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelected(level.id); } }}>
            <line x1="16" x2="580" y1={level.lineY} y2={level.lineY} stroke={level.color} strokeWidth={active.id === level.id ? 2 : 1} strokeDasharray={level.id === 'current' ? '3 5' : '7 5'} />
            <path d={`M580 ${level.lineY} L602 ${level.labelY} L610 ${level.labelY}`} fill="none" stroke={level.color} opacity="0.7" />
            <rect x="605" y={level.labelY - 17} width="209" height="34" rx="4" fill={active.id === level.id ? '#25313e' : '#141b24'} stroke={level.color} strokeOpacity={active.id === level.id ? 0.8 : 0.2} />
            <text x="615" y={level.labelY - 3} fill={level.color} fontSize="11">{level.label}</text>
            <text x="615" y={level.labelY + 11} fill="#f3f6fa" fontSize="12" fontWeight="600">{priceText(level.price)}</text>
          </g>)}
          <text x="16" y="340" fill="#a3acb9" fontSize="10">VOLUME</text>
          <text x="16" y="402" fill="#a3acb9" fontSize="11">{timeText(firstTime)}</text>
          <text x="580" y="402" fill="#a3acb9" fontSize="11" textAnchor="end">{timeText(lastTime)}</text>
        </svg>
      </div>
      <div className="risk-chart__choices" aria-label="Explain a price level">
        {levels.map((level) => <button key={level.id} type="button" aria-pressed={active.id === level.id} onClick={() => setSelected(level.id)} style={{ '--level-color': level.color }}>
          <span>{level.label}</span><strong>{priceText(level.price)}</strong>
        </button>)}
      </div>
      <div className="risk-chart__explanation" aria-live="polite" style={{ borderColor: active.color }}>
        <h4>{active.label} · {priceText(active.price)}</h4><p>{active.why}</p>
      </div>
      <p className="risk-chart__hint">Quote as of {timeText(plan.price_as_of)} · Last candle closed {timeText(chart.last_close_at)} · Times shown in your local timezone. This is a snapshot; refresh Risk Levels for an updated plan.</p>
      <p className="risk-chart__hint">Suggested prices are reference levels, not exchange-validated order prices. Check the market pair and allowed price increment before entering them. A stop-limit can remain unfilled if price gaps below the limit. <a href="https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/order-types" target="_blank" rel="noreferrer">How stop-limit orders work</a></p>
    </section>
  );
}
