import { useEffect, useRef, useState } from 'react';
import { UiButton, UiCard } from '../components/ui/DesignSystem.jsx';
import { parseHistory } from '../utils/macroChart.js';
import './chart-worker-status.css';

const STATUS_URL = '/.runtime/chart-worker/status.json';
const HISTORY_URL = '/.runtime/chart-worker/history.json';
const SCHEMA = 'moonwalking.chart-worker-status/v1';
const STATES = { idle: 'Waiting for its first run', running: 'Refreshing history', ok: 'Last run completed', error: 'Last run failed' };
const iso = (value) => value === null || (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value) && Number.isFinite(Date.parse(value)));
const boundedText = (value, max) => typeof value === 'string' && value.length > 0 && value.length <= max;
const TOPICS = { position: 'Current position', levels: 'Price references', limits: 'What this cannot establish' };

function validNarration(value) {
  if (value == null) return true; // Older worker files remain readable.
  return value.schema_version === 'moonwalking.chart-narration/v1'
    && ['local_ai', 'cached', 'fallback'].includes(value.state)
    && boundedText(value.model, 120) && iso(value.generated_at)
    && typeof value.evidence_sha256 === 'string' && /^[a-f0-9]{64}$/i.test(value.evidence_sha256)
    && (value.reason === null || boundedText(value.reason, 1000))
    && (value.elapsed_seconds === null || (typeof value.elapsed_seconds === 'number'
      && Number.isFinite(value.elapsed_seconds) && value.elapsed_seconds >= 0 && value.elapsed_seconds <= 86400))
    && Array.isArray(value.paragraphs) && value.paragraphs.length > 0 && value.paragraphs.length <= 6
    && value.paragraphs.every((paragraph) => paragraph && Object.hasOwn(TOPICS, paragraph.topic)
      && boundedText(paragraph.text, 4000) && Array.isArray(paragraph.fact_ids)
      && paragraph.fact_ids.length > 0 && paragraph.fact_ids.length <= 20
      && paragraph.fact_ids.every((id) => boundedText(id, 160)));
}

function checkedStatus(value) {
  if (!value || value.schema_version !== SCHEMA || !/^[A-Z0-9]{1,20}-USD$/.test(value.product_id)
    || !Object.hasOwn(STATES, value.state) || !Number.isSafeInteger(value.run_count) || value.run_count < 0
    || !['last_attempt_at', 'last_success_at', 'next_run_at'].every((key) => iso(value[key]))
    || !(value.last_error === null || typeof value.last_error === 'string')
    || !(value.candle_through_utc === null || /^\d{4}-\d{2}-\d{2}$/.test(value.candle_through_utc))
    || !(value.history_sha256 == null || (typeof value.history_sha256 === 'string' && /^[a-f0-9]{64}$/i.test(value.history_sha256)))
    || !(value.generation_id == null || (typeof value.generation_id === 'string' && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(value.generation_id)))
    || ![value.changed, value.analysis_changed].every((v) => v === null || typeof v === 'boolean')
    || !validNarration(value.narration_detail)
    || !Array.isArray(value.change_summary) || value.change_summary.some((line) => typeof line !== 'string')) {
    throw new Error('The local worker status file is invalid.');
  }
  return value;
}

function timestamp(value) {
  return value ? new Date(value).toISOString().replace('T', ' ').replace('.000Z', ' UTC') : 'Not recorded yet';
}

// Only the development server exposes local runtime files. There is no worker endpoint in production.
export default function ChartWorkerStatus({ onHistory }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const [readAt, setReadAt] = useState(null);
  const [opening, setOpening] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const historyRequest = useRef(null);
  const mounted = useRef(true);
  useEffect(() => {
    if (!import.meta.env.DEV) return undefined;
    mounted.current = true;
    let disposed = false;
    let active = null;
    const poll = async () => {
      if (active) return;
      const controller = new AbortController();
      active = controller;
      const timeout = setTimeout(() => controller.abort(), 15000);
      try {
        const response = await fetch(STATUS_URL, { cache: 'no-store', credentials: 'omit', signal: controller.signal });
        if (!response.ok) throw new Error(`Status file returned HTTP ${response.status}.`);
        const next = checkedStatus(await response.json());
        if (!disposed) { setStatus(next); setError(''); setReadAt(new Date().toISOString()); }
      } catch (problem) {
        if (!disposed) setError(problem.name === 'AbortError' ? 'The status read timed out.' : problem.message);
      } finally { clearTimeout(timeout); active = null; }
    };
    poll();
    const interval = setInterval(poll, 30000);
    return () => { disposed = true; mounted.current = false; clearInterval(interval); active?.abort(); historyRequest.current?.abort(); };
  }, []);

  if (!import.meta.env.DEV) return null;
  const overdue = status?.next_run_at && Date.parse(status.next_run_at) < Date.now() - 60000;
  const stale = Boolean(error || status?.state === 'error' || overdue);
  const narration = status?.narration_detail;
  async function openHistory() {
    historyRequest.current?.abort();
    const controller = new AbortController();
    historyRequest.current = controller;
    const timeout = setTimeout(() => controller.abort(), 15000);
    setOpening(true); setHistoryError('');
    try {
      const response = await fetch(HISTORY_URL, { cache: 'no-store', credentials: 'omit', signal: controller.signal });
      if (!response.ok) throw new Error(`History file returned HTTP ${response.status}.`);
      const encodedHistory = await response.text();
      if (status.history_sha256) {
        if (!globalThis.crypto?.subtle) throw new Error('This browser cannot verify the local history checksum.');
        const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(encodedHistory));
        const sha = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
        if (sha !== status.history_sha256.toLowerCase()) throw new Error('Worker history does not match this status snapshot. Wait for its next completed run, then try again.');
      }
      const history = parseHistory(JSON.parse(encodedHistory));
      if (history.instrument.product_id !== status.product_id) throw new Error('Worker history and status identify different coins.');
      if (status.generation_id || status.history_sha256) {
        const latestResponse = await fetch(STATUS_URL, { cache: 'no-store', credentials: 'omit', signal: controller.signal });
        if (!latestResponse.ok) throw new Error(`Status confirmation returned HTTP ${latestResponse.status}.`);
        const latest = checkedStatus(await latestResponse.json());
        if (latest.product_id !== status.product_id || latest.generation_id !== status.generation_id
          || latest.history_sha256?.toLowerCase() !== status.history_sha256?.toLowerCase()) {
          throw new Error('Worker output changed while opening the chart. Wait for its next completed run, then try again.');
        }
      }
      if (mounted.current && !controller.signal.aborted) onHistory(history);
    } catch (problem) {
      if (mounted.current && !controller.signal.aborted) setHistoryError(`${problem.message} Your current chart has been kept.`);
      else if (mounted.current && historyRequest.current === controller) setHistoryError('History loading stopped. Your current chart has been kept.');
    } finally {
      clearTimeout(timeout);
      if (mounted.current && historyRequest.current === controller) setOpening(false);
    }
  }
  return <UiCard className="chart-worker-status" aria-label="Local chart worker">
    <div className="chart-worker-status__heading"><div><span className="macro-label">Local single-coin pilot</span><h2>Automatic chart updates</h2></div>
      <span className="chart-worker-status__badge">{!status ? error ? 'Worker unavailable' : 'Checking worker' : stale ? 'Stale · check worker' : STATES[status.state]}</span></div>
    <p>This PC refreshes completed candles and calculates evidence. {narration
      ? 'A local model can select which verified facts to emphasize.'
      : 'Explanations are deterministic; no language model is connected.'}</p>
    {!status && !error && <p role="status">Looking for the local worker status…</p>}
    {error && <p role="alert">Local status unavailable: {error}{status ? ' Showing the last status received; it may be out of date.' : ' Start the local worker to create its status file.'}</p>}
    {status && <>
      <h3>{status.product_id} · {STATES[status.state]}</h3>
      {overdue && <p>The scheduled run is overdue. The worker may be stopped or this PC may have been asleep.</p>}
      {status.last_error && <p role="alert">Worker reported: {status.last_error}</p>}
      <dl className="chart-worker-status__dates">
        <div><dt>Last attempt</dt><dd>{timestamp(status.last_attempt_at)}</dd></div>
        <div><dt>Last successful run</dt><dd>{timestamp(status.last_success_at)}</dd></div>
        <div><dt>Next planned check</dt><dd>{timestamp(status.next_run_at)}</dd></div>
        <div><dt>Completed daily history through</dt><dd>{status.candle_through_utc || 'Not recorded yet'}</dd></div>
      </dl>
      <p>{status.run_count} run{status.run_count === 1 ? '' : 's'} recorded. {status.analysis_changed === true ? 'Chart analysis changed on the last run.' : status.analysis_changed === false ? 'No chart analysis change on the last run.' : 'No analysis comparison recorded yet.'}</p>
      {status.change_summary.length > 0 && <ul>{status.change_summary.map((line, index) => <li key={index}>{line}</li>)}</ul>}
      {narration && <section className="chart-worker-status__narration" aria-label="Saved worker explanation">
        <h3>{narration.state === 'fallback' ? 'Chart explanation · fallback' : 'Local AI chart explanation'}</h3>
        <p>{status.product_id} · Saved worker explanation{narration.generated_at ? ` · ${timestamp(narration.generated_at)}` : ' · Generation time not recorded'}.</p>
        {stale ? <p className="chart-worker-status__stale-explanation">This explanation comes from the last saved worker output. The status is stale; a refreshed explanation is not confirmed.</p>
          : status.state === 'running' && <p>A check is running. This saved explanation has not been refreshed by that check yet.</p>}
        {narration.state === 'fallback' ? <p>The local AI did not produce an accepted selection. Showing the deterministic evidence explanation.{narration.reason ? ` Reason: ${narration.reason}` : ''}</p>
          : <p>Local AI selects emphasis; prices and wording are verified templates. Model: {narration.model}.{narration.state === 'cached' ? ' Reused for unchanged evidence.' : ''}</p>}
        {narration.paragraphs.map((paragraph, index) => <div key={index} className="chart-worker-status__paragraph">
          <h4>{TOPICS[paragraph.topic]}</h4><p>{paragraph.text}</p>
        </div>)}
      </section>}
      <small>Last status read: {timestamp(readAt)}. Planned checks may start late if this PC is asleep or a run takes longer. This checks a local file every 30 seconds; it does not start or control the worker.</small>
      {onHistory && <div className="chart-worker-status__action"><UiButton onClick={openHistory} loading={opening} disabled={!status.last_success_at} loadingLabel="Opening worker chart…">Open worker chart</UiButton><small>Opens the saved worker history when you choose; background runs do not replace your current chart.</small></div>}
      {historyError && <p role="alert">{historyError}</p>}
    </>}
  </UiCard>;
}
