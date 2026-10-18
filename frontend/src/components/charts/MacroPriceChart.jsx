import { useId, useState } from 'react';
import { dateText, priceScale, priceText } from '../../utils/macroChart.js';

const WIDTH = 1120;
const HEIGHT = 500;
const LEFT = 24;
const TOP = 40;
const BOTTOM = 448;
const HISTORY_RIGHT = 855;
const LEVEL_RIGHT = 1008;

export default function MacroPriceChart({ candles, pivots, scenario, currency, interval, scale = 'log' }) {
  const id = useId().replace(/:/g, '');
  const [hover, setHover] = useState(null);
  if (!candles.length) return null;
  const valid = scenario && !scenario.error;
  const projected = valid ? [...scenario.levels, ...scenario.targets].map((row) => row.price) : [];
  const axis = priceScale(candles.flatMap((row) => [row.low, row.high]).concat(valid ? [scenario.invalidation, ...projected] : []), scale);
  const first = candles[0].time;
  const last = candles.at(-1).time;
  const duration = Math.max(interval, last - first + interval);
  const x = (time) => LEFT + ((time - first + interval / 2) / duration) * (HISTORY_RIGHT - LEFT);
  const y = (price) => BOTTOM - axis.position(price) * (BOTTOM - TOP);
  const candleWidth = Math.max(1, Math.min(13, ((HISTORY_RIGHT - LEFT) * interval / duration) * 0.65));
  const selected = candles[Math.max(0, Math.min(candles.length - 1, hover ?? candles.length - 1))];
  const visiblePivots = pivots.filter((pivot) => pivot.time >= first && pivot.time <= last);
  const ticks = axis.ticks;
  const dates = [...new Set([0, Math.floor(candles.length / 3), Math.floor(candles.length * 2 / 3), candles.length - 1])];

  const move = (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    const coordinate = ((event.clientX - rect.left) / rect.width) * WIDTH;
    const time = first + ((coordinate - LEFT) / (HISTORY_RIGHT - LEFT)) * duration - interval / 2;
    let closest = 0;
    candles.forEach((row, index) => {
      if (Math.abs(row.time - time) < Math.abs(candles[closest].time - time)) closest = index;
    });
    setHover(closest);
  };

  return (
    <figure className="macro-price-chart">
      <div className="macro-chart-viewport"><svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-labelledby={`${id}-title ${id}-description`}
        tabIndex={0} onMouseMove={move} onMouseLeave={() => setHover(null)}
        onKeyDown={(event) => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          setHover((current) => event.key === 'Home' ? 0 : event.key === 'End' ? candles.length - 1
            : Math.max(0, Math.min(candles.length - 1, (current ?? candles.length - 1) + (event.key === 'ArrowLeft' ? -1 : 1))));
        }}>
        <title id={`${id}-title`}>Historical price candles and conditional Fibonacci levels</title>
        <desc id={`${id}-description`}>Solid candles and selected swing anchors are historical. Dashed horizontal levels are calculated scenarios with no forecast date. Use the left and right arrow keys to inspect candles.</desc>
        <defs><clipPath id={`${id}-clip`}><rect x={LEFT} y={TOP} width={LEVEL_RIGHT - LEFT} height={BOTTOM - TOP} /></clipPath></defs>
        {ticks.map((price) => <g key={price} className="macro-chart-grid">
          <line x1={LEFT} y1={y(price)} x2={LEVEL_RIGHT} y2={y(price)} />
          <text x={LEVEL_RIGHT + 12} y={y(price) + 4}>{priceText(price, currency)}</text>
        </g>)}
        <text className="macro-chart-note" x={LEFT} y={22}>COMPLETED PRICE HISTORY · {scale.toUpperCase()} SCALE</text>
        <text className="macro-chart-note" x={HISTORY_RIGHT + 8} y={22}>LEVELS ONLY</text>
        <line className="macro-chart-boundary" x1={HISTORY_RIGHT} y1={TOP} x2={HISTORY_RIGHT} y2={BOTTOM} />
        <g clipPath={`url(#${id}-clip)`}>
          {valid && <>
            <rect className="macro-chart-zone macro-chart-zone--pullback" x={LEFT} width={LEVEL_RIGHT - LEFT}
              y={y(scenario.pullback_zone[1])} height={y(scenario.pullback_zone[0]) - y(scenario.pullback_zone[1])} />
            <rect className="macro-chart-zone macro-chart-zone--target" x={HISTORY_RIGHT} width={LEVEL_RIGHT - HISTORY_RIGHT}
              y={y(scenario.target_zone[1])} height={Math.max(1, y(scenario.target_zone[0]) - y(scenario.target_zone[1]))}>
              <title>Extension band: 1–1.618 times the measured move, projected from C</title>
            </rect>
            {scenario.levels.map((level) => <line key={level.ratio} className="macro-chart-fib" x1={LEFT} x2={LEVEL_RIGHT} y1={y(level.price)} y2={y(level.price)} />)}
            {scenario.targets.map((level) => <line key={level.ratio} className="macro-chart-target" x1={x(scenario.anchors[2].time)} x2={LEVEL_RIGHT} y1={y(level.price)} y2={y(level.price)} />)}
            <line className="macro-chart-invalidation" x1={LEFT} x2={LEVEL_RIGHT} y1={y(scenario.invalidation)} y2={y(scenario.invalidation)} />
          </>}
          {candles.map((row) => <g key={row.time} className={`macro-candle macro-candle--${row.close >= row.open ? 'up' : 'down'}`}>
            <title>{dateText(row.time)} · Open {priceText(row.open, currency)} · High {priceText(row.high, currency)} · Low {priceText(row.low, currency)} · Close {priceText(row.close, currency)}</title>
            <line x1={x(row.time)} x2={x(row.time)} y1={y(row.high)} y2={y(row.low)} />
            <rect x={x(row.time) - candleWidth / 2} y={Math.min(y(row.open), y(row.close))}
              width={candleWidth} height={Math.max(1.5, Math.abs(y(row.open) - y(row.close)))} />
          </g>)}
          {visiblePivots.map((pivot) => <circle className="macro-chart-pivot" key={pivot.id} cx={x(pivot.time)} cy={y(pivot.price)} r={3}>
            <title>{pivot.type} {dateText(pivot.extreme_time ?? pivot.time)} · Confirmed {dateText(pivot.confirmed_at)}</title>
          </circle>)}
          {valid && <polyline className="macro-chart-anchors" points={scenario.anchors.map((anchor) => `${x(anchor.time)},${y(anchor.price)}`).join(' ')} />}
          {valid && scenario.anchors.map((anchor, index) => <g key={anchor.id}>
            <circle className="macro-chart-anchor" cx={x(anchor.time)} cy={y(anchor.price)} r={5} />
            <text className="macro-chart-anchor-label" x={x(anchor.time)} y={y(anchor.price) + (anchor.type === 'high' ? -15 : 23)} textAnchor="middle">{'ABC'[index]}</text>
          </g>)}
          {hover !== null && <line className="macro-chart-crosshair" x1={x(selected.time)} x2={x(selected.time)} y1={TOP} y2={BOTTOM} />}
        </g>
        {dates.map((index) => <text key={index} className="macro-chart-date" x={x(candles[index].time)} y={HEIGHT - 17} textAnchor="middle">{dateText(candles[index].time)}</text>)}
      </svg></div>
      <figcaption>
        <strong>{dateText(selected.time)}</strong>
        <span>{interval === 7 * 86400 ? 'Week beginning' : 'UTC day'}</span>
        <span>O {priceText(selected.open, currency)}</span><span>H {priceText(selected.high, currency)}</span>
        <span>L {priceText(selected.low, currency)}</span><span>C {priceText(selected.close, currency)}</span>
        <span>Volume {selected.volume.toLocaleString('en-US', { maximumFractionDigits: 2 })}</span>
      </figcaption>
    </figure>
  );
}
