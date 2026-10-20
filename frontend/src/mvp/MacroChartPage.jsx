import { useEffect, useMemo, useRef, useState } from 'react';
import { UiButton, UiCard, UiChip, UiField } from '../components/ui/DesignSystem.jsx';
import MacroPriceChart from '../components/charts/MacroPriceChart.jsx';
import ChartCoinSearch from './ChartCoinSearch.jsx';
import ChartTimingPanel from './ChartTimingPanel.jsx';
import ChartLevelGuide, { guideEvidence } from './ChartLevelGuide.jsx';
import ChartWorkerStatus from './ChartWorkerStatus.jsx';
import { DAY, WEEK, aggregateWeeks, chartAt, confirmedPivots, dateText, defaultAnchors, fibScenario, parseHistory, priceText } from '../utils/macroChart.js';
import { defaultMacroAnchors, historicalMacro, macroRange, recentSwingSequence } from '../utils/chartStructure.js';
import { nextRunMap } from '../utils/nextRunMap.js';
import { publicHistoryClient } from '../utils/publicChartHistory.js';
import { historyFreshness, requireCurrentHistory } from '../utils/chartFreshness.js';
import '../styles/macro-chart.css';

const STATUS = {
  conditional: 'Conditional scenario', invalidated: 'A anchor touched',
  target_touched: 'First extension touched', both_touched_order_unknown: 'Extension and A anchor touched · order ungraded',
};

function ChartWorkspace({ history }) {
  const [timeframe, setTimeframe] = useState('1w');
  const [date, setDate] = useState(dateText(history.captured_at - 1));
  const [confirmation, setConfirmation] = useState(2);
  const [focusRange, setFocusRange] = useState(null);
  const cutoff = Math.floor(Date.parse(`${date}T00:00:00Z`) / 1000) + DAY;
  const chart = useMemo(() => chartAt(history, timeframe, Number.isFinite(cutoff) ? cutoff : 0), [history, timeframe, cutoff]);
  const daily = useMemo(() => chartAt(history, '1d', chart.as_of).candles, [history, chart.as_of]);
  const displayChart = useMemo(() => focusRange ? chartAt(history, focusRange.interval, chart.as_of) : chart,
    [history, focusRange?.interval, chart]);
  const detected = useMemo(() => confirmedPivots(chart.candles, {
    left: confirmation, right: confirmation, interval: chart.interval_seconds,
  }), [chart, confirmation]);
  const { instrument } = history;
  return <>
    <UiCard className="macro-controls">
      <div className="macro-segment" role="group" aria-label="Candle interval">
        {['1w', '1d'].map((value) => <UiButton key={value} size="sm" aria-pressed={timeframe === value}
          variant={timeframe === value ? 'primary' : 'secondary'} onClick={() => { setFocusRange(null); setTimeframe(value); }}>{value === '1w' ? 'Weekly' : 'Daily'}</UiButton>)}
      </div>
      <UiField type="date" label="Replay through (UTC)" value={date} min={dateText(history.candles[0].time)}
        max={dateText(history.captured_at)} onInput={(event) => { setFocusRange(null); setDate(event.currentTarget.value); }}
        onChange={(event) => { setFocusRange(null); setDate(event.target.value); }} />
      <label className="macro-select">Swing confirmation
        <select value={confirmation} onChange={(event) => { setFocusRange(null); setConfirmation(Number(event.target.value)); }}>
          {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} completed bars each side</option>)}
        </select>
      </label>
    </UiCard>
    <div className="macro-provenance">
      <span>{instrument.venue} · {instrument.quote_currency}</span>
      <span>Export cutoff {dateText(history.captured_at)} · Replay through {dateText(chart.as_of - 1)} UTC</span>
      <span>{chart.missing_days} missing daily intervals · {chart.excluded_weeks} incomplete weeks excluded</span>
    </div>
    {detected.ambiguous > 0 && <p className="macro-muted">{detected.ambiguous} candles were both a local high and low. Their swing order is ambiguous and they were excluded.</p>}
    <ScenarioWorkspace key={`${timeframe}-${date}-${confirmation}`} chart={chart} pivots={detected.pivots} instrument={instrument}
      dailyCandles={daily} confirmation={confirmation} displayChart={displayChart} focusRange={focusRange}
      onResetFocus={() => setFocusRange(null)} onInspect={(start, end) => {
        setFocusRange({ start, end, interval: end - start > 360 * DAY ? '1w' : '1d' });
      }} />
  </>;
}

function ScenarioWorkspace({ chart, pivots, instrument, dailyCandles, confirmation, displayChart, focusRange, onInspect, onResetFocus }) {
  const plotRef = useRef(null);
  const guideRef = useRef(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState(null);
  const wasFocused = useRef(false);
  const [scale, setScale] = useState('log');
  const [anchorIds, setAnchorIds] = useState(() => defaultAnchors(pivots));
  const [macroIds, setMacroIds] = useState(() => defaultMacroAnchors(pivots));
  const [showMacro, setShowMacro] = useState(false);
  const [showHistory, setShowHistory] = useState(true);
  const [showFuture, setShowFuture] = useState(false);
  const [showRecent, setShowRecent] = useState(false);
  const [showLocal, setShowLocal] = useState(false);
  const [futureRatio, setFutureRatio] = useState(0.786);
  const [count, setCount] = useState(Math.min(displayChart.interval_seconds === 7 * DAY ? 52 : 160, Math.max(20, displayChart.candles.length)));
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    if (!focusRange || !displayChart.candles.length) {
      if (wasFocused.current) {
        setOffset(0); setCount(Math.min(400, displayChart.candles.length));
        setShowMacro(false); setShowHistory(true); setShowFuture(false);
      }
      wasFocused.current = false;
      return;
    }
    wasFocused.current = true;
    const match = displayChart.candles.findIndex((c) => c.end > focusRange.start);
    const first = Math.max(0, (match < 0 ? displayChart.candles.length - 20 : match) - 3);
    const after = displayChart.candles.findIndex((c) => c.time > focusRange.end);
    const endIndex = Math.min(displayChart.candles.length, (after < 0 ? displayChart.candles.length : after) + 3);
    setCount(Math.min(400, Math.max(20, endIndex - first)));
    setOffset(Math.max(0, displayChart.candles.length - endIndex));
    setShowMacro(false); setShowHistory(false); setShowFuture(false); setShowRecent(false); setShowLocal(false);
    plotRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }, [focusRange, displayChart.candles]);
  useEffect(() => { setSelectedEvidenceId(null); }, [macroIds]);
  const end = displayChart.candles.length - offset;
  const displayed = displayChart.candles.slice(Math.max(0, end - count), end);
  const anchors = anchorIds.map((id) => pivots.find((pivot) => pivot.id === id));
  const scenario = fibScenario(anchors, chart.candles);
  const macroAnchors = macroIds.map((id) => pivots.find((p) => p.id === id));
  const macro = macroRange(...macroAnchors, { asOf: chart.as_of });
  const structure = historicalMacro(pivots, macro, { asOf: chart.as_of });
  const futureLevel = !macro.error ? macro.levels.find((p) => p.ratio === futureRatio) : null;
  const recentStructure = recentSwingSequence(pivots, { asOf: chart.as_of });
  const valid = !scenario.error;
  const format = (price) => priceText(price, instrument.quote_currency);
  const low = chart.candles.length ? chart.candles.reduce((a, b) => a.low < b.low ? a : b) : null;
  const high = chart.candles.length ? chart.candles.reduce((a, b) => a.high > b.high ? a : b) : null;
  const priorHigh = chart.candles.slice(0, -1).reduce((a, b) => !a || b.high > a.high ? b : a, null);
  const nextRun = nextRunMap(dailyCandles, { asOf: chart.as_of, confirmation, lookbackDays: 90 });
  const weeklyRun = nextRunMap(aggregateWeeks(dailyCandles).filter((p) => p.complete), {
    asOf: chart.as_of, confirmation, interval: WEEK, lookbackDays: 365,
  });
  const plotRun = chart.interval_seconds === WEEK ? weeklyRun : nextRun;
  const recentLevels = ['low', 'high'].flatMap((type) => {
    const p = pivots.filter((row) => row.type === type).at(-1);
    return p ? [{ ...p, label: `Recent ${type}` }] : [];
  });

  const evidence = guideEvidence(macro, recentLevels, structure.anchors || [], nextRun, weeklyRun);
  const selectedEvidence = [...evidence.nearby, ...evidence.observed, ...evidence.anchors, ...evidence.calculated].find((p) => p.id === selectedEvidenceId);
  const selectEvidence = (id) => {
    setSelectedEvidenceId(id);
    if (id.startsWith('ratio:')) { setFutureRatio(Number(id.slice(6))); if (!focusRange) setShowFuture(true); }
  };
  const explainFromChart = (id) => { setSelectedEvidenceId(id); guideRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }); };

  if (!chart.candles.length) return <UiCard><h2>No completed candles in this view</h2>
    <p>Choose a later replay date or switch to daily candles. Incomplete weeks are excluded.</p></UiCard>;

  return <>
    <div className="macro-stat-grid">
      <UiCard><span className="macro-label">Last completed close</span><strong className="macro-price">{format(chart.candles.at(-1).close)}</strong><small>Period ending {dateText(chart.candles.at(-1).end - 1)}</small></UiCard>
      <UiCard><span className="macro-label">Low in analysed history</span><strong>{format(low.low)}</strong><small>{dateText(low.low_time ?? low.time)} · Available venue history</small></UiCard>
      <UiCard><span className="macro-label">High in analysed history</span><strong>{format(high.high)}</strong><small>{dateText(high.high_time ?? high.time)} · Available venue history</small></UiCard>
    </div>
    <UiCard className="macro-reading" tone="subtle"><span className="macro-label">Your price map</span><h2>Focus on the next recovery</h2>
      <p>Compare the daily swing and the weekly cycle separately. The daily list uses turns from the last 90 days; the weekly list uses complete weekly turns from the last year. Neither estimates how long a move will take.</p>
      <p>Clearing one reference only exceeds that particular prior high; other recent highs may still be overhead. It would not establish a return to the old cycle peak or a new high across the full history. We have not established the next run's final high.</p>
      {priorHigh && chart.candles.at(-1).close > priorHigh.high && <p>The last completed close is already above the previous historical high of {format(priorHigh.high)} in this view. Old recovery ratios still describe their original historical range.</p>}
      <a className="macro-timing-link" href="#macro-future">See the next-run checkpoints</a>
    </UiCard>
    <div ref={guideRef}><ChartLevelGuide macro={macro} nextRun={nextRun} weeklyRun={weeklyRun} evidence={evidence} latest={chart.candles.at(-1)}
      currency={instrument.quote_currency} interval={chart.interval_seconds} selectedId={selectedEvidenceId}
      onSelect={selectEvidence} onInspect={onInspect} focusRange={focusRange} /></div>
    <UiCard className="macro-range-panel">
      <div className="macro-range-header"><div><span className="macro-label">Historical drawdown reference</span><h2>Macro price range</h2></div>
        <label className="macro-range-toggle"><input type="checkbox" checked={showMacro} disabled={!!focusRange} onChange={(event) => setShowMacro(event.target.checked)} />Show long-range macro band</label></div>
      <details className="macro-advanced"><summary>Adjust historical anchors</summary><div className="macro-range-grid">
        {['High', 'Low'].map((name, index) => <label className="macro-select" key={name}>{name} · Confirmed swing
          <select aria-label={`Macro ${name.toLowerCase()}`} value={macroIds[index]} onChange={(event) => setMacroIds((current) => current.map((id, i) => i === index ? event.target.value : id))}>
            <option value="">Select a confirmed {name.toLowerCase()}</option>
            {pivots.filter((p) => p.type === name.toLowerCase()).map((p) => <option key={p.id} value={p.id}>{dateText(p.extreme_time ?? p.time)} · {format(p.price)}</option>)}
          </select>
          {macroAnchors[index] && <small>Confirmable {dateText(macroAnchors[index].confirmed_at)}</small>}
        </label>)}
        <div className="macro-range-result">{macro.error ? <p className="macro-muted">{macro.error}</p> : <>
          <span className="macro-label">50–78.6% recovery reference</span><strong>{format(macro.recovery_band[0])}–{format(macro.recovery_band[1])}</strong>
          <small>Available from {dateText(macro.available_at)}</small>
        </>}</div>
      </div>
      <div className="macro-range-description"><UiButton size="sm" onClick={() => setMacroIds(defaultMacroAnchors(pivots))}>Use observed range</UiButton>
        <p>Default: highest confirmed high, then the lowest confirmed low after it. Linear-price Fibonacci levels describe this selected range; they do not establish a wave count or a likely destination.</p></div>
      </details>
      <div className="macro-structure-controls">
        <label className="macro-range-toggle"><input type="checkbox" checked={showHistory} disabled={!!focusRange} onChange={(event) => setShowHistory(event.target.checked)} />Show historical A–D</label>
        <label className="macro-range-toggle"><input type="checkbox" checked={showRecent} disabled={!!focusRange} onChange={(event) => setShowRecent(event.target.checked)} />Show smaller a–d</label>
        <label className="macro-range-toggle"><input type="checkbox" checked={showFuture && !macro.error} disabled={!!macro.error || !!focusRange} onChange={(event) => setShowFuture(event.target.checked)} />Show long-range macro scenario</label>
        {showFuture && futureLevel && <label className="macro-select">Long-range E? reference
          <select aria-label="Future reference level" value={futureRatio} onChange={(event) => { setFutureRatio(Number(event.target.value)); setSelectedEvidenceId(`ratio:${event.target.value}`); }}>
            {[0.5, 0.618, 0.786, 1, 1.618].map((r) => <option key={r} value={r}>{r === 1.618 ? '1.618× extension' : `${(r * 100).toFixed(1)}% recovery`} · {format(macro.levels.find((p) => p.ratio === r).price)}</option>)}
          </select>
        </label>}
      </div>
      {showHistory && !structure.error && <>
        <div className="macro-structure-evidence" aria-label="Historical macro anchors">{structure.anchors.map((p) => <span key={p.label}><strong>{p.label}</strong> {dateText(p.extreme_time ?? p.time)} · {format(p.price)}<small>Confirmed {dateText(p.confirmed_at)}</small></span>)}</div>
        <p>Historical anchor names, not a validated wave count. A is the highest confirmed high before B; B is the lowest confirmed low before the selected macro high C; D is the selected later low.{!structure.complete && ' Earlier A/B anchors are incomplete in this view.'}</p>
      </>}
      {showFuture && futureLevel && <p className="macro-future-note">E? is a hypothetical price reference at {format(futureLevel.price)}, drawn from the last completed close when that candle is visible. Its horizontal position does not estimate a date or probability.</p>}
      {showRecent && <p>Small letters restart for the latest four alternating turns inside the larger move. They are a separate scale, not proof of a repeating pattern. Chart angles change with zoom; matching patterns would need comparisons of percentage moves and time.</p>}
    </UiCard>
    <div className="macro-workspace" ref={plotRef}>
      <UiCard className="macro-chart-panel" padding="none">
        <div className="macro-chart-heading"><div><span className="macro-label">{instrument.symbol} / {instrument.quote_currency}</span><h2>The larger move</h2></div>
          <UiChip tone={showLocal && valid && scenario.status === 'invalidated' ? 'danger' : 'neutral'}>{showLocal && valid ? STATUS[scenario.status] : 'Historical structure'}</UiChip></div>
        <MacroPriceChart candles={displayed} pivots={pivots} scenario={showLocal ? scenario : null} macro={showMacro ? macro : null} referenceLevels={[...plotRun.above, ...plotRun.below].map((p) => ({ ...p, reference_interval: chart.interval_seconds === WEEK ? 'weekly' : 'daily' }))}
          historical={showHistory ? structure.anchors : []} future={showFuture ? futureLevel : null}
          nested={showRecent ? recentStructure : []}
          selectedEvidence={selectedEvidence} onSelectAnchor={(p) => explainFromChart(`anchor:${p.id}`)}
          onSelectFuture={() => explainFromChart(`ratio:${futureRatio}`)}
          latestCandle={chart.candles.at(-1)}
          currency={instrument.quote_currency} interval={displayChart.interval_seconds} scale={scale} />
        {focusRange && <p className="macro-focus-note">Focused on {dateText(focusRange.start)}–{dateText(focusRange.end)} UTC, with surrounding {displayChart.interval_seconds === DAY ? 'daily' : 'weekly'} candles, up to 400 at once. Replay cutoff unchanged; the original analysis and selected levels are unchanged. Large overlays are hidden for inspection. Use Fit history to return.</p>}
        <div className="macro-chart-navigation">
          <label className="macro-select">Price display
            <select aria-label="Price display" value={scale} onChange={(event) => setScale(event.target.value)}>
              <option value="log">Logarithmic</option><option value="linear">Linear</option>
            </select>
          </label>
          <UiButton size="sm" disabled={end <= Math.min(count, displayChart.candles.length)} onClick={() => setOffset(Math.min(displayChart.candles.length - count, offset + Math.ceil(count / 3)))}>Earlier</UiButton>
          <UiButton size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - Math.ceil(count / 3)))}>Later</UiButton>
          <UiButton size="sm" onClick={() => { onResetFocus(); setOffset(0); setCount(Math.min(400, chart.candles.length)); if (focusRange) { setShowMacro(false); setShowHistory(true); setShowFuture(false); } }}>Fit history</UiButton>
          {displayChart.candles.length > 20 && <label>Visible candles <input aria-label="Visible candles" type="range" min={20} max={Math.min(400, displayChart.candles.length)} value={Math.min(count, displayChart.candles.length)} onChange={(event) => { setCount(Number(event.target.value)); setOffset(0); }} /></label>}
        </div>
        <div className="macro-chart-legend"><span>Solid: historical swings</span>{showHistory && <span>A–D: historical macro anchors</span>}{showFuture && futureLevel && <span>Dashed E?: hypothetical future reference</span>}<span>H/L: prior {chart.interval_seconds === WEEK ? 'weekly' : 'daily'} highs and lows</span>{showLocal && valid && <span>Dashed horizontals: local Fibonacci levels</span>}{showMacro && !macro.error && <span>Mint band: selected macro recovery range</span>}<span>Future timing is not estimated</span><span className="macro-mobile-hint">Swipe the chart to inspect its full width</span></div>
      </UiCard>
      <UiCard className="macro-anchor-panel">
        <details className="macro-advanced"><summary>Optional: measure a smaller move</summary>
        <label className="macro-range-toggle"><input type="checkbox" checked={showLocal} disabled={!!focusRange} onChange={(event) => setShowLocal(event.target.checked)} />Show local measurement</label>
        <span className="macro-label">Local measurement</span><h2>Three swing anchors</h2>
        <p>A → B defines the measured move. C defines the pullback or rebound.</p>
        {'ABC'.split('').map((letter, index) => <label className="macro-select" key={letter}>{letter} · {['Move starts', 'Move ends', 'Correction ends'][index]}
          <select aria-label={`Anchor ${letter}`} value={anchorIds[index] || ''} onChange={(event) => setAnchorIds((current) => Array.from({ length: 3 }, (_, i) => i === index ? event.target.value : current[i] || ''))}>
            <option value="">Select a confirmed swing</option>
            {pivots.map((pivot) => <option key={pivot.id} value={pivot.id}>{dateText(pivot.extreme_time ?? pivot.time)} · {pivot.type} · {format(pivot.price)}</option>)}
          </select>
          {anchors[index] && <small>Confirmable {dateText(anchors[index].confirmed_at)}</small>}
        </label>)}
        <UiButton size="sm" onClick={() => setAnchorIds(defaultAnchors(pivots))}>Use latest swings</UiButton>
        <p className="macro-muted">A/B/C are selected anchor names. A full Elliott Wave count has not been established.</p>
        </details>
      </UiCard>
    </div>
    <ChartTimingPanel macroAnchors={structure.anchors} recentAnchors={recentStructure} levels={recentLevels}
      dailyCandles={dailyCandles} asOf={chart.as_of} currency={instrument.quote_currency} onFocus={onInspect} />
    <details className="macro-advanced"><summary>Details of the local measurement</summary>{valid ? <div className="macro-scenario-grid">
      <UiCard><span className="macro-label">Pullback reference · 38.2–61.8%</span><h2>{format(scenario.pullback_zone[0])}–{format(scenario.pullback_zone[1])}</h2><p>Measured within A → B. C retraced {(scenario.retracement * 100).toFixed(1)}% of that move.</p></UiCard>
      <UiCard><span className="macro-label">{scenario.direction === 'up' ? 'Upside' : 'Downside'} extension · 1–1.618×</span><h2>{format(scenario.target_zone[0])}–{format(scenario.target_zone[1])}</h2><p>Projected from C using the length of A → B. A price scenario, with no forecast date or measured success rate.</p></UiCard>
      <UiCard><span className="macro-label">Selected A anchor</span><h2>{format(scenario.invalidation)}</h2><p>Measurement available from {dateText(scenario.available_at)}. Anchor touches are recorded only on subsequent completed candles; their order is ungraded.</p></UiCard>
    </div> : <UiCard tone="subtle"><h2>No qualifying local measurement</h2><p role="status">{scenario.error}</p><p>The automatic historical map and larger recovery references remain available. You do not need to choose anchors.</p></UiCard>}</details>
  </>;
}

export default function MacroChartPage({ initialHistory = null, historyClient = publicHistoryClient }) {
  const [history, setHistory] = useState(initialHistory);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [remoteBusy, setRemoteBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const loadId = useRef(0);
  const refreshRequest = useRef(null);
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 30000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => () => { loadId.current += 1; refreshRequest.current?.abort(); }, []);
  const freshness = history ? historyFreshness(history, clock) : null;
  const quote = history?.source?.latest_trade;
  const validQuote = quote && typeof quote.price === 'number' && Number.isFinite(quote.price) && quote.price > 0
    && Number.isFinite(Date.parse(quote.trade_at)) && Number.isFinite(Date.parse(quote.checked_at))
    && Date.parse(quote.checked_at) <= clock + 60000 && Date.parse(quote.trade_at) <= Date.parse(quote.checked_at) + 60000;
  const stamp = (value) => value && Number.isFinite(Date.parse(value)) ? new Date(value).toISOString().replace('T', ' ').replace(/\.\d+Z$/, ' UTC') : 'Not recorded';
  async function refreshLatest() {
    refreshRequest.current?.abort();
    const controller = new AbortController(); refreshRequest.current = controller;
    const id = ++loadId.current;
    setLoading(true); setError('');
    try {
      const next = await historyClient.history(history.instrument.product_id, {
        signal: controller.signal, force: true, includeLatestTrade: true,
      });
      requireCurrentHistory(next, Date.now());
      if (id === loadId.current && !controller.signal.aborted) {
        setHistory(next); setClock(Date.now()); setRevision((r) => r + 1);
      }
    } catch (failure) {
      if (id === loadId.current && failure.name !== 'AbortError') setError(`${failure.message} Your previous chart has been kept.`);
    } finally { if (id === loadId.current) setLoading(false); }
  }
  const load = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    refreshRequest.current?.abort();
    const id = ++loadId.current;
    setLoading(true); setError('');
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('Choose a history file smaller than 10 MB.');
      const parsed = parseHistory(JSON.parse(await file.text()));
      if (id === loadId.current) { setHistory(parsed); setRevision((current) => current + 1); }
    } catch (failure) {
      if (id === loadId.current) setError(failure instanceof SyntaxError ? 'This file is not valid JSON. Your previous chart has been kept.' : failure.message);
    } finally {
      if (id === loadId.current) setLoading(false);
    }
  };
  return <div className="macro-page mw-app">
    <nav className="macro-topbar" aria-label="Chart navigation"><a href="/">BHABIT / Moonwalking</a>{import.meta.env.DEV && <a href="/chart-map?worker=1">Local worker</a>}<a href="/design-system">Design system</a></nav>
    <main className="macro-main">
      <header className="macro-intro"><div><p className="mw-eyebrow">Long-term chart map</p><h1>Read the larger move.</h1><p>Historical turning points, measured pullbacks, and conditional price zones.</p></div><UiChip tone="accent">Research preview</UiChip></header>
      {import.meta.env.DEV && new URLSearchParams(window.location.search).get('worker') === '1' && <ChartWorkerStatus onHistory={(next) => { loadId.current += 1; setLoading(false); setHistory(next); setRevision((r) => r + 1); setError(''); }} />}
      <ChartCoinSearch client={historyClient} hasHistory={!!history} onBusyChange={setRemoteBusy} onBegin={() => { refreshRequest.current?.abort(); loadId.current += 1; setLoading(false); setError(''); }}
        onHistory={(next) => { setHistory(next); setRevision((r) => r + 1); setError(''); }} />
      {history && <>
        <div className="macro-loaded"><strong>{history.instrument.symbol} history loaded</strong><span>{history.instrument.venue} · Daily history through {freshness.through_utc ?? 'unavailable'} UTC</span></div>
        <UiCard tone="subtle" aria-label="Chart data freshness">
          <h2>{freshness.current ? 'Latest completed daily candle present' : 'Historical snapshot · refresh required'}</h2>
          <p>Actual candles through {freshness.through_utc ?? 'unavailable'} UTC · Expected through {freshness.expected_through_utc} UTC. The current UTC day is still forming; weekly calculations use complete weeks.</p>
          <p>History fetched: {stamp(freshness.checked_at)}. Saved files do not refresh themselves.</p>
          {validQuote ? <p>Latest reported trade: <strong>{priceText(quote.price, history.instrument.quote_currency)}</strong> · Trade time {stamp(quote.trade_at)} · Provider checked {stamp(quote.checked_at)}.{clock - Date.parse(quote.checked_at) > 120000 ? ' Quote check is over two minutes old; refresh to check again.' : ''} This is a trade snapshot; completed-candle calculations retain their dated closes.</p>
            : <p>Latest reported trade is unavailable in this snapshot.{history.source?.latest_trade_error ? ` ${history.source.latest_trade_error}` : ''} Refresh to check it.</p>}
          <UiButton disabled={loading || remoteBusy} onClick={refreshLatest}>Refresh latest data</UiButton>
        </UiCard>
      </>}
      {loading && <p role="status">Checking historical prices…</p>}
      {error && <p className="macro-error" role="alert">{error}</p>}
      {history ? <ChartWorkspace key={`${history.instrument.product_id}-${history.captured_at}-${revision}`} history={history} />
        : <UiCard className="macro-empty"><div className="macro-empty-mark" aria-hidden="true">A → B → C</div><h2>Search a coin to build its price map</h2><p>Enter a symbol above and select the coin. We load its available history and mark turning points and possible recovery levels automatically.</p><span>No coin selected · No projected prices</span></UiCard>}
      <details className="macro-advanced"><summary>Advanced: use a saved history file</summary><UiField type="file" accept="application/json,.json" label={history ? 'Replace price history' : 'Load price history'}
        onChange={load} disabled={loading || remoteBusy} hint="Optional local import. Your file is read in this browser and is not uploaded." /></details>
      <footer className="macro-footer">Chart levels describe a selected price structure. Predictive performance has not been established. Manual anchor selection is exploratory.</footer>
    </main>
  </div>;
}
