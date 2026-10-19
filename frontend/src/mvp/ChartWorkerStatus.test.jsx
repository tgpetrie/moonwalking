import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ChartWorkerStatus from './ChartWorkerStatus.jsx';
import { syntheticHistory } from '../test/macroHistory.test.fixture.js';
import { createHash, webcrypto } from 'node:crypto';
import { TextEncoder } from 'node:util';

// Synthetic local status and price fixtures, not market observations.
const status = () => ({ schema_version: 'moonwalking.chart-worker-status/v1', product_id: 'TEST-USD', state: 'ok',
  last_attempt_at: '2026-10-18T18:00:00Z', last_success_at: '2026-10-18T18:00:00Z', next_run_at: '2026-10-18T19:00:00Z',
  last_error: null, candle_through_utc: '2026-10-17', reference_close: null, changed: true,
  change_summary: ['Completed history advanced by one day.'], run_count: 2, analysis_changed: false,
  history_path: 'https://untrusted.example/history.json' });
const response = (value) => ({ ok: true, json: async () => value, text: async () => JSON.stringify(value) });
async function settle() { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); }
beforeEach(() => {
  vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-18T18:15:00Z')); vi.stubEnv('DEV', true);
  vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('TextEncoder', TextEncoder);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe('local chart worker status', () => {
  it('polls only the fixed local file and never opens history without an explicit click', async () => {
    const fetch = vi.fn().mockResolvedValue(response(status())); vi.stubGlobal('fetch', fetch);
    const onHistory = vi.fn(); render(<ChartWorkerStatus onHistory={onHistory} />); await settle();
    expect(screen.getByText('TEST-USD · Last run completed')).toBeVisible();
    expect(screen.getByText('2026-10-17')).toBeVisible();
    expect(screen.getByText(/No chart analysis change/)).toBeVisible();
    expect(screen.getByText(/no language model is connected/)).toBeVisible();
    expect(fetch).toHaveBeenCalledTimes(1); expect(fetch.mock.calls[0][0]).toBe('/.runtime/chart-worker/status.json');
    expect(fetch.mock.calls[0][1]).toMatchObject({ cache: 'no-store', credentials: 'omit' });
    expect(onHistory).not.toHaveBeenCalled();
    fetch.mockResolvedValueOnce(response(syntheticHistory()));
    fireEvent.click(screen.getByRole('button', { name: 'Open worker chart' })); await settle();
    expect(fetch.mock.calls[1][0]).toBe('/.runtime/chart-worker/history.json');
    expect(onHistory).toHaveBeenCalledTimes(1); expect(onHistory.mock.calls[0][0].instrument.product_id).toBe('TEST-USD');
  });
  it('keeps last valid status visibly stale after a failed or malformed poll and recovers', async () => {
    const fetch = vi.fn().mockResolvedValue(response(status())); vi.stubGlobal('fetch', fetch);
    render(<ChartWorkerStatus />); await settle();
    fetch.mockRejectedValueOnce(new Error('File unavailable'));
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(screen.getByText('Stale · check worker')).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('Showing the last status received');
    expect(screen.getByText('TEST-USD · Last run completed')).toBeVisible();
    fetch.mockResolvedValueOnce(response({ schema_version: 'wrong' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(screen.getByRole('alert')).toHaveTextContent('invalid');
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByText('Stale · check worker')).not.toBeInTheDocument();
  });
  it('does not replace the current chart with invalid or mismatched history', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response(status())).mockResolvedValueOnce(response({ candles: [] }));
    vi.stubGlobal('fetch', fetch); const onHistory = vi.fn();
    render(<ChartWorkerStatus onHistory={onHistory} />); await settle();
    fireEvent.click(screen.getByRole('button', { name: 'Open worker chart' })); await settle();
    expect(screen.getByRole('alert')).toHaveTextContent('Your current chart has been kept');
    expect(onHistory).not.toHaveBeenCalled();
    const other = syntheticHistory(); other.instrument.product_id = 'OTHER-USD';
    fetch.mockResolvedValueOnce(response(other));
    fireEvent.click(screen.getByRole('button', { name: 'Open worker chart' })); await settle();
    expect(screen.getByRole('alert')).toHaveTextContent('different coins');
    expect(onHistory).not.toHaveBeenCalled();
  });
  it('aborts active reads and clears polling on unmount', async () => {
    const fetch = vi.fn(() => new Promise(() => {})); vi.stubGlobal('fetch', fetch);
    const view = render(<ChartWorkerStatus />); await settle();
    const signal = fetch.mock.calls[0][1].signal;
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(fetch).toHaveBeenCalledTimes(1); // No overlapping request.
    view.unmount(); expect(signal.aborted).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(90000); });
    expect(fetch).toHaveBeenCalledTimes(1); expect(vi.getTimerCount()).toBe(0);
  });
  it('shows overdue scheduling honestly and never fetches production runtime files', async () => {
    const old = status(); old.next_run_at = '2026-10-18T17:00:00Z';
    const fetch = vi.fn().mockResolvedValue(response(old)); vi.stubGlobal('fetch', fetch);
    const view = render(<ChartWorkerStatus />); await settle();
    expect(screen.getByText(/scheduled run is overdue/)).toBeVisible(); view.unmount();
    vi.stubEnv('DEV', false); render(<ChartWorkerStatus />); await settle();
    expect(fetch).toHaveBeenCalledTimes(1); expect(screen.queryByLabelText('Local chart worker')).not.toBeInTheDocument();
  });
  it('verifies exact history bytes and generation before opening a chart', async () => {
    vi.useRealTimers();
    const history = syntheticHistory();
    const guarded = { ...status(), generation_id: '06b6fcd7-bfea-4041-a1c8-bc97e322ddc2',
      history_sha256: createHash('sha256').update(JSON.stringify(history)).digest('hex') };
    const fetch = vi.fn().mockResolvedValueOnce(response(guarded)).mockResolvedValueOnce(response(history))
      .mockResolvedValueOnce(response(guarded)); vi.stubGlobal('fetch', fetch);
    const onHistory = vi.fn(); render(<ChartWorkerStatus onHistory={onHistory} />); await settle();
    fireEvent.click(screen.getByRole('button', { name: 'Open worker chart' }));
    await waitFor(() => expect(onHistory).toHaveBeenCalledTimes(1));
    expect(onHistory).toHaveBeenCalledTimes(1); expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      '/.runtime/chart-worker/status.json', '/.runtime/chart-worker/history.json', '/.runtime/chart-worker/status.json',
    ]);
    expect(screen.getByText('Next planned check')).toBeVisible();
  });
  it('keeps the current chart if history bytes or publication generation change', async () => {
    vi.useRealTimers();
    const history = syntheticHistory();
    const guarded = { ...status(), generation_id: '06b6fcd7-bfea-4041-a1c8-bc97e322ddc2',
      history_sha256: createHash('sha256').update(JSON.stringify(history)).digest('hex') };
    const changed = syntheticHistory(); changed.candles[0].volume += 1;
    const fetch = vi.fn().mockResolvedValueOnce(response(guarded)).mockResolvedValueOnce(response(changed));
    vi.stubGlobal('fetch', fetch); const onHistory = vi.fn(); render(<ChartWorkerStatus onHistory={onHistory} />); await settle();
    fireEvent.click(screen.getByRole('button', { name: 'Open worker chart' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('does not match this status snapshot'));
    expect(screen.getByRole('alert')).toHaveTextContent('does not match this status snapshot');
    expect(onHistory).not.toHaveBeenCalled(); expect(fetch).toHaveBeenCalledTimes(2);
    fetch.mockResolvedValueOnce(response(history)).mockResolvedValueOnce(response({ ...guarded, generation_id: '441c09b7-0230-46a9-9b8c-697a071eea4f' }));
    fireEvent.click(screen.getByRole('button', { name: 'Open worker chart' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('changed while opening'));
    expect(screen.getByRole('alert')).toHaveTextContent('changed while opening');
    expect(onHistory).not.toHaveBeenCalled();
  });
  it('rejects malformed optional generation/checksum fields', async () => {
    const fetch = vi.fn().mockResolvedValue(response({ ...status(), history_sha256: 'not-a-hash', generation_id: '../output' }));
    vi.stubGlobal('fetch', fetch); render(<ChartWorkerStatus />); await settle();
    expect(screen.getByRole('alert')).toHaveTextContent('status file is invalid');
    expect(screen.queryByText('TEST-USD · Last run completed')).not.toBeInTheDocument();
  });
});
