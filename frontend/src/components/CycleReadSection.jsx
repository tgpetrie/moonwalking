import React from 'react';
import { plainPrice } from './WaveStructureOverlay.jsx';
import '../styles/cycle-read.css';

/*
 * CycleReadSection
 * ----------------
 * The multi-year read for the Chart Read panel's Cycle horizon. It renders
 * three parts of GET /api/chart-read/<symbol>?horizon=cycle as sent:
 *   multi_year_context     RSI regimes, weekly StochRSI, monthly exhaustion,
 *                          weekly SMA ladder
 *   top_down_confluence    confirmation pivot, invalidation stop, Fibonacci
 *                          overlaps, the two target tiers and which is active
 *   macro_industry_regime  the industry gate that picks the active tier
 *
 * Descriptive only. Nothing here is outcome-validated, and a value the
 * backend did not send renders as unavailable rather than as a number.
 *
 * Colour follows docs/DESIGN_SYSTEM.md: every chip here is a STATUS
 * (ok / caution / danger / muted), never amber-or-violet price direction.
 */

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const price = (value) => plainPrice(value) || '—';
const fixed = (value, digits = 1) => (finite(value) ? value.toFixed(digits) : '—');
const signedPct = (value) => (finite(value) ? `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toFixed(1)}%` : null);

export const GATE_BADGE = {
  risk_on_aligned: { label: 'Risk-on aligned', tone: 'ok' },
  neutral_chop: { label: 'Neutral chop', tone: 'muted' },
  risk_off_headwind: { label: 'Risk-off headwind', tone: 'danger' },
};

// Below 40 is compression, above 60 is expansion; 40 and 60 themselves sit in
// no-man's-land, matching cycle_analysis.rsi_regime.
export const RSI_REGIME = {
  oversold_compression: { label: 'Below 40 · oversold compression', tone: 'caution' },
  no_mans_land: { label: "40–60 · no-man's-land", tone: 'muted' },
  growth_expansion: { label: 'Above 60 · growth expansion', tone: 'ok' },
  unavailable: { label: 'Not enough history', tone: 'muted' },
};

const RSI_TIMEFRAMES = [['1d', '1D'], ['1w', '1W'], ['1m', '1M']];

export const STOCH_STATE = {
  oversold_turn_up: { label: 'Oversold, turning up', tone: 'ok' },
  overbought_turn_down: { label: 'Overbought, turning down', tone: 'caution' },
  bullish_expansion: { label: 'Rising · %K above %D', tone: 'ok' },
  high_to_low_drift: { label: 'Drifting lower · %K below %D', tone: 'muted' },
};

const STOP_BASIS = {
  wave_c_low: "the last leg's low",
  double_bottom_low: 'the double-bottom low',
};

const TIER_UNAVAILABLE = {
  no_macro_drawdown: 'No pullback of 20% or more from the cycle high to measure.',
  cycle_high_is_latest_bar: 'Price is at its cycle high, so there is no pullback to measure.',
  drawdown_under_20_pct: 'The pullback from the cycle high is under 20%.',
  no_secondary_range: 'No counter-rally inside the decline to extend from.',
};

function Badge({ tone = 'muted', children, ...rest }) {
  return <span className={`cycle-read__badge cycle-read__badge--${tone}`} {...rest}>{children}</span>;
}

function GateRow({ top, regime }) {
  const gateKey = top?.macro_regime_gate || (regime?.available ? regime.macro_regime_gate : null);
  const badge = GATE_BADGE[gateKey];
  const reasons = Array.isArray(regime?.reasons) ? regime.reasons : [];
  return (
    <div className="cycle-read__gate" data-testid="cycle-gate">
      <span className="cycle-read__label">Industry gate</span>
      {badge ? (
        <Badge tone={badge.tone} data-testid="cycle-gate-badge" data-gate={gateKey}>{regime?.gate_label || badge.label}</Badge>
      ) : (
        <Badge data-testid="cycle-gate-badge" data-gate="unavailable">
          {regime?.reason === 'warming' ? 'Warming up' : 'Unavailable'}
        </Badge>
      )}
      {regime?.available && regime.stage_label ? <span className="cycle-read__text">{regime.stage_label}</span> : null}
      {reasons.length ? <span className="cycle-read__faint">{reasons[reasons.length - 1]}</span> : null}
    </div>
  );
}

function RsiTile({ timeframe, block }) {
  const regime = RSI_REGIME[block?.regime] || RSI_REGIME.unavailable;
  const value = finite(block?.value) ? block.value : null;
  return (
    <div className="cycle-read__tile" data-testid={`cycle-rsi-${timeframe.toLowerCase()}`} data-regime={block?.regime || 'unavailable'}>
      <span className="cycle-read__label">{timeframe} RSI</span>
      <strong className="cycle-read__number">{value === null ? '—' : fixed(value)}</strong>
      {/* 0–100 track with the 40 and 60 lines; the dot is the current value. */}
      <span className="cycle-read__track" aria-hidden="true">
        <span className="cycle-read__zone" />
        {value === null ? null : <span className="cycle-read__dot" style={{ left: `${Math.min(100, Math.max(0, value))}%` }} />}
      </span>
      <Badge tone={regime.tone}>{regime.label}</Badge>
      {block?.near_bull_support ? <span className="cycle-read__faint">Near 40 support in an uptrend</span> : null}
    </div>
  );
}

function StochTile({ stoch }) {
  const state = STOCH_STATE[stoch?.direction];
  const ready = Boolean(stoch?.available && state);
  return (
    <div className="cycle-read__tile" data-testid="cycle-stoch" data-direction={ready ? stoch.direction : 'unavailable'}>
      <span className="cycle-read__label">1W StochRSI</span>
      <strong className="cycle-read__number">
        {ready ? `${fixed(stoch.weekly_stoch_rsi_k, 0)} / ${fixed(stoch.weekly_stoch_rsi_d, 0)}` : '—'}
      </strong>
      <span className="cycle-read__faint">%K / %D</span>
      <Badge tone={ready ? state.tone : 'muted'}>{ready ? state.label : 'Needs more weekly history'}</Badge>
    </div>
  );
}

function ExhaustionTile({ exhaustion }) {
  const ready = Boolean(exhaustion?.available);
  const streak = finite(exhaustion?.monthly_bearish_streak) ? exhaustion.monthly_bearish_streak : null;
  const threshold = finite(exhaustion?.streak_threshold) ? exhaustion.streak_threshold : null;
  const exhausted = Boolean(ready && exhaustion.multi_year_oversold_exhaustion);
  let note = null;
  if (ready && exhaustion.histogram_shrinking === null) note = 'Monthly MACD is still warming up';
  else if (ready && exhaustion.histogram_shrinking) note = 'Negative monthly MACD histogram is shrinking';
  else if (ready) note = 'No shrinking negative monthly MACD histogram';
  return (
    <div className="cycle-read__tile" data-testid="cycle-exhaustion" data-exhausted={exhausted ? 'true' : 'false'}>
      <span className="cycle-read__label">1M bear streak</span>
      <strong className="cycle-read__number">
        {ready && streak !== null ? `${streak}${threshold !== null ? ` / ${threshold}` : ''}` : '—'}
      </strong>
      <span className="cycle-read__faint">bearish months{threshold !== null ? ' / needed' : ''}</span>
      {!ready ? <Badge>Needs more monthly history</Badge>
        : exhausted ? <Badge tone="ok" data-testid="cycle-exhaustion-badge">Multi-year exhaustion</Badge>
          : <Badge>Not exhausted</Badge>}
      {note ? <span className="cycle-read__faint">{note}</span> : null}
    </div>
  );
}

function SmaLadder({ ladder }) {
  const levels = Array.isArray(ladder?.levels) ? ladder.levels : [];
  if (!levels.length) return null;
  return (
    <div className="cycle-read__block" data-testid="cycle-sma-ladder">
      <p className="cycle-read__heading">Weekly SMA ladder</p>
      <ul className="cycle-read__rows">
        {levels.map((level) => (
          <li key={level.key} className="cycle-read__row" data-testid={`cycle-${level.key}`} data-role={level.role || 'unavailable'}>
            <span className="cycle-read__row-name">{level.period}W SMA</span>
            {level.available && finite(level.value) ? (
              <>
                <span className="cycle-read__price">{price(level.value)}</span>
                <Badge tone={level.role === 'support' ? 'ok' : 'muted'}>
                  {level.role === 'support' ? 'Below price · support' : 'Above price · resistance'}
                </Badge>
                <span className="cycle-read__faint">{signedPct(level.distance_pct) || ''}</span>
              </>
            ) : (
              <span className="cycle-read__faint">
                Needs {level.bars_needed || level.period} weekly bars
                {finite(ladder.weekly_bars) ? ` · ${ladder.weekly_bars} so far` : ''}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function PivotAndStop({ top, context }) {
  const pivot = top?.low_confirmation_pivot || context?.daily_structure?.low_confirmation_pivot || null;
  const atSupport = Boolean(top?.low_confirmation_pivot);
  const breakout = top?.confirmation_breakout || context?.daily_structure?.confirmation_breakout || {};
  const stop = top?.accumulation_invalidation_stop || null;
  return (
    <div className="cycle-read__block" data-testid="cycle-levels">
      <p className="cycle-read__heading">Confirmation and invalidation</p>
      <ul className="cycle-read__rows">
        <li className="cycle-read__row" data-testid="cycle-pivot">
          <span className="cycle-read__row-name">Low-confirmation pivot</span>
          {pivot && finite(pivot.price) ? (
            <>
              <span className="cycle-read__price">{price(pivot.price)}</span>
              <span className="cycle-read__faint">{signedPct(pivot.distance_pct) ? `${signedPct(pivot.distance_pct)} from price` : ''}</span>
              <span className="cycle-read__text">
                {atSupport && pivot.message ? pivot.message
                  : top ? 'The last swing high above price. Price is not at multi-year support, so a break is not read as a cycle low.'
                    : 'The last swing high above price.'}
              </span>
            </>
          ) : (
            <span className="cycle-read__faint">No swing high above price in the last 180 days.</span>
          )}
        </li>
        {breakout.broken ? (
          <li className="cycle-read__row" data-testid="cycle-breakout">
            <span className="cycle-read__row-name">Pivot break</span>
            <span className="cycle-read__price">{price(breakout.pivot_price)}</span>
            <Badge tone={breakout.recent ? 'ok' : 'muted'}>
              Closed above it {finite(breakout.bars_since_break) ? `${breakout.bars_since_break} day${breakout.bars_since_break === 1 ? '' : 's'} ago` : ''}
            </Badge>
          </li>
        ) : null}
        <li className="cycle-read__row" data-testid="cycle-stop">
          <span className="cycle-read__row-name">Accumulation invalidation</span>
          {stop && finite(stop.stop_price) ? (
            <>
              <span className="cycle-read__price cycle-read__price--danger">{price(stop.stop_price)}</span>
              {stop.tight ? <Badge tone="caution">Tight</Badge> : null}
              <span className="cycle-read__text">
                {stop.message || `Accumulation read is invalid below ${price(stop.stop_price)}`}
              </span>
              {STOP_BASIS[stop.basis] ? (
                <span className="cycle-read__faint">{fixed(stop.buffer_pct, 0)}% under {STOP_BASIS[stop.basis]}</span>
              ) : null}
            </>
          ) : (
            <span className="cycle-read__faint">
              {top ? 'None. Price is not inside the multi-year accumulation area.' : 'Not available.'}
            </span>
          )}
        </li>
      </ul>
    </div>
  );
}

function Clusters({ clusters }) {
  const list = Array.isArray(clusters) ? clusters : [];
  return (
    <div className="cycle-read__block" data-testid="cycle-clusters">
      <p className="cycle-read__heading">Fibonacci confluence</p>
      {list.length ? (
        <ul className="cycle-read__rows">
          {list.map((cluster) => (
            <li key={`${cluster.retracement_ratio}-${cluster.extension_ratio}`} className="cycle-read__row" data-testid="cycle-cluster">
              <span className="cycle-read__price">{price(cluster.low)}–{price(cluster.high)}</span>
              <span className="cycle-read__text">
                {cluster.retracement_ratio} retracement meets {cluster.extension_ratio} extension
              </span>
              <span className="cycle-read__faint">
                {[signedPct(cluster.distance_pct) ? `${signedPct(cluster.distance_pct)} from price` : null,
                  finite(cluster.spread_pct) ? `${cluster.spread_pct}% apart` : null].filter(Boolean).join(' · ')}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="cycle-read__faint">The retracement grid and the extension grid do not overlap anywhere.</p>
      )}
    </div>
  );
}

const POSITION_TEXT = { below: 'Price is below the zone', inside: 'Price is inside the zone', above: 'Price is above the zone' };

function TierCard({ testId, title, tier, active, children }) {
  return (
    <div className={`cycle-read__tier${active ? ' is-active' : ''}`} data-testid={testId} data-active={active ? 'true' : 'false'}>
      <div className="cycle-read__tier-head">
        <span className="cycle-read__label">{title}</span>
        <Badge tone={active ? 'ok' : 'muted'}>{active ? 'Active expectation' : 'Reference only'}</Badge>
      </div>
      {tier?.available ? children : (
        <p className="cycle-read__faint">{TIER_UNAVAILABLE[tier?.reason] || 'Not available for this coin.'}</p>
      )}
    </div>
  );
}

function TargetTiers({ top }) {
  const box = top?.rollover_target_box;
  const full = top?.full_extension_targets;
  if (!box && !full) return null;
  const activeTier = top?.active_target_tier || 'rollover_target_box';
  const confluence = Array.isArray(box?.extension_confluence) ? box.extension_confluence : [];
  const targets = Array.isArray(full?.targets) ? full.targets : [];
  return (
    <div className="cycle-read__block" data-testid="cycle-targets" data-active-tier={activeTier}>
      <p className="cycle-read__heading">Upside targets · two tiers</p>
      <div className="cycle-read__tiers">
        <TierCard testId="cycle-rollover-box" title="Tier 1 · Rollover zone (conservative)" tier={box} active={activeTier === 'rollover_target_box'}>
          <strong className="cycle-read__range">{price(box?.low)}–{price(box?.high)}</strong>
          <span className="cycle-read__faint">{POSITION_TEXT[box?.price_position] || ''}</span>
          <ul className="cycle-read__levels">
            {Object.entries(box?.levels || {}).map(([ratio, value]) => (
              <li key={ratio}><span>{ratio}</span><span className="cycle-read__price">{price(value)}</span></li>
            ))}
          </ul>
          {confluence.length ? (
            <span className="cycle-read__faint">
              Also a {confluence.map((item) => `${item.ratio} extension at ${price(item.price)}`).join(' and ')}
            </span>
          ) : null}
        </TierCard>
        <TierCard testId="cycle-full-extension" title="Tier 2 · Full extension targets" tier={full} active={activeTier === 'full_extension_targets'}>
          <ul className="cycle-read__levels">
            {targets.map((target) => (
              <li key={target.ratio} data-confluence={target.confluence ? 'true' : 'false'}>
                <span>{target.ratio}</span>
                <span className="cycle-read__price">{price(target.price)}</span>
                <span className="cycle-read__faint">{signedPct(target.distance_pct) || ''}</span>
                {target.confluence ? <Badge tone="ok">confluence</Badge> : null}
              </li>
            ))}
          </ul>
        </TierCard>
      </div>
      <p className="cycle-read__faint">
        The industry gate picks the active tier: stages 1–2 read the rollover zone, stages 3–4 the full extensions.
        Both are log-scale Fibonacci levels, not forecasts.
      </p>
    </div>
  );
}

const isNum = (value) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
const coinCount = (value) => (isNum(value)
  ? Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
  : '—');

export function CycleReplayStrip({ backtest }) {
  if (!backtest?.available) return null;
  const extra = Number(backtest.extra_coins_pct);
  const reduction = Number(backtest.drawdown_reduction_pct);
  const cycles = Number(backtest.completed_trim_reload_cycles) || 0;
  return (
    <div className="cycle-read__block" data-testid="cycle-replay">
      <p className="cycle-read__heading">Historical cycle replay</p>
      <div className="cycle-read__tiles cycle-read__tiles--replay">
        <div className="cycle-read__tile" data-testid="cycle-replay-coins">
          <span className="cycle-read__label">Compounded vs HODL</span>
          <strong className="cycle-read__number">
            {coinCount(backtest.compounded_final_coins)} / {coinCount(backtest.hodl_final_coins)}
          </strong>
          <span className={`cycle-read__faint${isNum(extra) && extra > 0 ? ' cycle-read__faint--ok' : ''}`}>
            {isNum(extra) ? `${extra >= 0 ? '+' : ''}${extra.toFixed(1)}% coins` : 'coins held at the end'}
          </span>
        </div>
        <div className="cycle-read__tile" data-testid="cycle-replay-equivalent">
          <span className="cycle-read__label">Coin-equivalent stack</span>
          <strong className="cycle-read__number">{coinCount(backtest.strategy_final_coin_equivalent)}</strong>
          <span className="cycle-read__faint">coins plus any USDC at the last close</span>
        </div>
        <div className="cycle-read__tile" data-testid="cycle-replay-drawdown">
          <span className="cycle-read__label">Max DD reduction</span>
          <strong className="cycle-read__number">
            {isNum(reduction) ? `${reduction >= 0 ? '−' : '+'}${Math.abs(reduction).toFixed(1)} pts` : '—'}
          </strong>
          <span className="cycle-read__faint">
            {isNum(backtest.max_drawdown_strategy_pct) && isNum(backtest.max_drawdown_hodl_pct)
              ? `${Number(backtest.max_drawdown_strategy_pct).toFixed(1)}% vs ${Number(backtest.max_drawdown_hodl_pct).toFixed(1)}% HODL`
              : 'max drawdown'}
          </span>
        </div>
        <div className="cycle-read__tile" data-testid="cycle-replay-cycles">
          <span className="cycle-read__label">Completed trim→reload cycles</span>
          <strong className="cycle-read__number">{cycles}</strong>
          <span className="cycle-read__faint">all three rungs refilled</span>
        </div>
      </div>
      <p className="cycle-read__faint">
        Simplified rule replay over this coin&apos;s daily history, starting from 100 coins with no added cash.
        {backtest.ended_stopped_out ? ' It ends stopped out in USDC.' : ''} Not a forecast and not outcome tested.
      </p>
    </div>
  );
}

export default function CycleReadSection({ context, top, regime }) {
  if (!context?.available) return null;
  const regimes = context.rsi_regimes || {};
  const pattern = top?.available ? top.cycle_pattern : null;
  const confluence = top?.available ? top : null;
  return (
    <div className="cycle-read" data-testid="cycle-read">
      <p className="cycle-read__title">Cycle read · multi-year</p>
      <GateRow top={confluence} regime={regime} />
      {pattern?.description ? <p className="cycle-read__text" data-testid="cycle-pattern">{pattern.description}</p> : null}

      {context.cycle_momentum_error ? (
        <p className="cycle-read__faint" data-testid="cycle-momentum-error">Momentum reads are unavailable for this coin right now.</p>
      ) : (
        <div className="cycle-read__tiles" data-testid="cycle-momentum">
          {RSI_TIMEFRAMES.map(([key, label]) => <RsiTile key={key} timeframe={label} block={regimes[key]} />)}
          <StochTile stoch={context.weekly_stoch_rsi} />
          <ExhaustionTile exhaustion={context.monthly_cycle_exhaustion} />
        </div>
      )}

      <div className="cycle-read__columns">
        <SmaLadder ladder={context.weekly_sma_ladder} />
        <PivotAndStop top={confluence} context={context} />
      </div>

      {confluence ? (
        <>
          <TargetTiers top={confluence} />
          <Clusters clusters={confluence.fib_confluence_clusters} />
        </>
      ) : (
        <p className="cycle-read__faint" data-testid="cycle-top-unavailable">
          Targets and confirmation levels need a full multi-year history for this coin.
        </p>
      )}

      <CycleReplayStrip backtest={context.backtest} />

      <p className="cycle-read__faint">
        {context.is_multi_year === false ? 'Under a year of clean daily history, so these reads are thin. ' : ''}
        Descriptive only. None of this has been tested against outcomes.
      </p>
    </div>
  );
}
