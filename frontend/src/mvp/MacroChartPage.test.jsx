import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { syntheticHistory } from '../test/macroHistory.test.fixture.js';
import { parseHistory } from '../utils/macroChart.js';
import disclosures from '../utils/chartDisclosures.json';
import MacroChartPage from './MacroChartPage.jsx';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

// Existing manual-geometry checks exercise the optional tools explicitly.
function renderWithTools(ui) {
  const view = render(ui);
  for (const name of ['Adjust historical anchors', 'Optional: measure a smaller move', 'Details of the local measurement']) {
    fireEvent.click(screen.getByText(name, { selector: 'summary' }));
  }
  fireEvent.click(screen.getByRole('checkbox', { name: 'Show local measurement' }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'Show long-range macro band' }));
  return view;
}

describe('local long-term chart workspace', () => {
  it('refreshes explicit runs and keeps latest-trade context separate from dated candle calculations', async () => {
    const now = Date.UTC(2026, 9, 20, 12);
    const time = vi.spyOn(Date, 'now').mockReturnValue(now);
    try {
      const fresh = syntheticHistory();
      const shift = Date.UTC(2026, 9, 20) / 1000 - fresh.captured_at;
      fresh.candles = fresh.candles.map((p) => ({ ...p, start: p.start + shift, end: p.end + shift }));
      fresh.captured_at += shift;
      fresh.source = { fetched_at: new Date(now).toISOString(), latest_trade: {
        price: 24.6, trade_at: '2026-10-20T11:59:00Z', checked_at: new Date(now).toISOString(),
      } };
      const old = { ...fresh, candles: fresh.candles.slice(0, -1), source: {} };
      const client = { history: vi.fn().mockResolvedValue(parseHistory(fresh)) };
      const { container } = render(<MacroChartPage initialHistory={parseHistory(old)} historyClient={client} />);
      expect(screen.getByRole('heading', { name: 'Historical snapshot · refresh required' })).toBeVisible();
      expect(screen.getByRole('region', { name: 'Chart data freshness' })).toHaveTextContent('Actual candles through 2026-10-18');
      fireEvent.click(screen.getByRole('button', { name: 'Refresh latest data' }));
      await waitFor(() => expect(screen.getByRole('heading', { name: 'Latest completed daily candle present' })).toBeVisible());
      expect(client.history).toHaveBeenCalledWith('TEST-USD', expect.objectContaining({ force: true, includeLatestTrade: true }));
      expect(screen.getByRole('region', { name: 'Chart data freshness' })).toHaveTextContent('Latest reported trade: $24.60');
      expect(container.querySelector('.next-run-baseline')).toHaveTextContent('$23.06');
    } finally { time.mockRestore(); }
  });
  it('does not replace a saved chart with a stale-tail result from a refresh attempt', async () => {
    const input = parseHistory(syntheticHistory());
    const client = { history: vi.fn().mockResolvedValue(input) };
    render(<MacroChartPage initialHistory={input} historyClient={client} />);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh latest data' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('not published'));
    expect(screen.getByRole('alert')).toHaveTextContent('Your previous chart has been kept');
    expect(screen.getByText('TEST history loaded')).toBeVisible();
  });
  it('shows both horizons and explains a weekly observation against its own dated close', () => {
    const input = syntheticHistory();
    input.candles.push(...Array.from({ length: 2 }, (_, i) => ({ start: input.captured_at + i * 86400,
      end: input.captured_at + (i + 1) * 86400, open: 24, close: 24, high: 24.3, low: 23.8, volume: 100, complete: true })));
    input.captured_at += 2 * 86400;
    const { container } = render(<MacroChartPage initialHistory={parseHistory(input)} />);
    expect(screen.getByRole('heading', { name: 'Daily swing · recent 90-day structure' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Weekly cycle references' })).toBeVisible();
    expect(screen.getByText(/Latest completed daily range:/)).toBeVisible();
    const button = screen.getByRole('button', { name: 'Explain Weekly prior high 1' });
    fireEvent.click(button);
    const explanation = container.querySelector('#macro-level-explanation');
    expect(explanation).toHaveTextContent('Weekly prior high 1');
    expect(explanation).toHaveTextContent('+6.1%');
    expect(explanation).toHaveTextContent('Confirmed');
    expect(screen.getByText(/Distances below use this weekly close/)).toBeVisible();
  });
  it('names prior observations and discloses the untested daily rule before any explanation is selected', () => {
    const { container } = render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    expect(screen.getByText(disclosures.daily_pivot_study, { exact: false })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Study scope and limitations' })).toHaveAttribute('href', disclosures.study_source);
    expect(screen.getByRole('heading', { name: 'Prior highs above the close' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Prior lows below the close' })).toBeVisible();
    const button = screen.getByRole('button', { name: 'Explain Prior high 1' });
    fireEvent.click(button);
    expect(screen.getByRole('heading', { name: /Prior high 1 ·/ })).toBeVisible();
    expect(container.querySelector('.macro-chart-reference text')).toHaveTextContent(/^[HL][123] /);
    expect(container.querySelector('.macro-next-run-grid').textContent).not.toMatch(/\b[RS][123]\b/);
    expect(container.querySelector('.macro-chart-legend')).toHaveTextContent('H/L: prior weekly highs and lows');
    fireEvent.input(screen.getByLabelText('Replay through (UTC)'), { target: { value: '2024-01-14' } });
    expect(screen.getByText(disclosures.daily_pivot_study, { exact: false })).toBeVisible();
    expect(screen.queryByRole('heading', { name: /Prior high 1 ·/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Explain Prior high 1' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('starts with an honest empty state and makes no API requests', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<MacroChartPage />);
    expect(screen.getByRole('heading', { name: 'Search a coin to build its price map' })).toBeVisible();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('plots completed weekly candles and exposes data coverage and scenario limits', () => {
    const { container } = renderWithTools(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    expect(container.querySelectorAll('.macro-candle')).toHaveLength(30);
    expect(screen.getByText('Low in analysed history')).toBeVisible();
    expect(screen.getByText('High in analysed history')).toBeVisible();
    expect(screen.getByText('Future timing is not estimated')).toBeVisible();
    expect(screen.getByText(/A full Elliott Wave count has not been established/)).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Anchor A' }).value).toMatch(/^low-/);
    expect(screen.getByText('Conditional scenario')).toBeVisible();
    expect(screen.getByText('Selected A anchor')).toBeVisible();
    expect(screen.getByText('Selected A anchor').closest('.ui-card').querySelector('h2').textContent)
      .toBe(screen.getByRole('combobox', { name: 'Anchor A' }).selectedOptions[0].textContent.split(' · ').at(-1));
    expect(screen.queryByText('Structural invalidation')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Load price history')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Change history file' })).not.toBeInTheDocument();
  });

  it('changes timeframe and withholds future candles and anchors during replay', () => {
    const { container } = renderWithTools(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    fireEvent.click(screen.getByRole('button', { name: 'Daily', exact: true }));
    expect(container.querySelectorAll('.macro-candle')).toHaveLength(160);
    fireEvent.input(screen.getByLabelText('Replay through (UTC)'), { target: { value: '2024-01-14' } });
    expect(container.querySelectorAll('.macro-candle')).toHaveLength(14);
    expect(screen.getByRole('combobox', { name: 'Anchor C' })).toHaveValue('');
    expect(screen.queryByText('Conditional scenario')).not.toBeInTheDocument();
  });

  it('rejects incompatible anchor ordering while retaining the historical chart', () => {
    renderWithTools(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const a = screen.getByRole('combobox', { name: 'Anchor A' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Anchor B' }), { target: { value: a.value } });
    expect(screen.getByRole('status')).toHaveTextContent('Anchor dates must follow A, then B, then C.');
    expect(screen.getByRole('img')).toBeVisible();
  });

  it('changes the display scale without changing the selected anchors or level prices', () => {
    const { container } = renderWithTools(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const levels = container.querySelector('.macro-scenario-grid').textContent;
    const a = screen.getByRole('combobox', { name: 'Anchor A' }).value;
    const macroLevels = container.querySelector('.macro-range-result').textContent;
    expect(screen.getByRole('combobox', { name: 'Price display' })).toHaveValue('log');
    fireEvent.change(screen.getByRole('combobox', { name: 'Price display' }), { target: { value: 'linear' } });
    expect(screen.getByText('COMPLETED PRICE HISTORY · LINEAR SCALE')).toBeVisible();
    expect(container.querySelector('.macro-scenario-grid').textContent).toBe(levels);
    expect(screen.getByRole('combobox', { name: 'Anchor A' })).toHaveValue(a);
    expect(container.querySelector('.macro-range-result').textContent).toBe(macroLevels);
  });

  it('edits and resets the macro range independently of local A/B/C geometry', () => {
    const { container } = renderWithTools(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const a = screen.getByRole('combobox', { name: 'Anchor A' }).value;
    const localLevels = container.querySelector('.macro-scenario-grid').textContent;
    const macroLow = screen.getByRole('combobox', { name: 'Macro low' });
    const originalLow = macroLow.value;
    const originalBand = container.querySelector('.macro-range-result').textContent;
    expect(container.querySelector('.macro-chart-recovery')).toBeInTheDocument();
    fireEvent.change(macroLow, { target: { value: '' } });
    expect(screen.getByText('Select a confirmed high and a later confirmed low.')).toBeVisible();
    expect(container.querySelector('.macro-chart-recovery')).not.toBeInTheDocument();
    fireEvent.change(macroLow, { target: { value: macroLow.options[1].value } });
    expect(screen.getByText('The macro range needs a high followed by a lower low.')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Use observed range' }));
    expect(macroLow).toHaveValue(originalLow);
    expect(container.querySelector('.macro-range-result').textContent).toBe(originalBand);
    expect(screen.getByRole('combobox', { name: 'Anchor A' })).toHaveValue(a);
    expect(container.querySelector('.macro-scenario-grid').textContent).toBe(localLevels);
  });

  it('toggles the macro band and removes future anchors during replay', () => {
    const { container } = renderWithTools(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const toggle = screen.getByRole('checkbox', { name: 'Show long-range macro band' });
    expect(container.querySelector('.macro-chart-recovery')).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(container.querySelector('.macro-chart-recovery')).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(container.querySelector('.macro-chart-recovery')).toBeInTheDocument();
    fireEvent.input(screen.getByLabelText('Replay through (UTC)'), { target: { value: '2024-01-14' } });
    expect(screen.getByRole('combobox', { name: 'Macro high' })).toHaveValue('');
    expect(screen.getByRole('combobox', { name: 'Macro low' })).toHaveValue('');
    expect(container.querySelector('.macro-chart-recovery')).not.toBeInTheDocument();
  });

  it('shows historical anchor labels even when local geometry does not qualify', () => {
    const input = syntheticHistory();
    input.candles.slice(14, 21).forEach((row) => { for (const key of ['open', 'high', 'low', 'close']) row[key] += 10; });
    const { container } = renderWithTools(<MacroChartPage initialHistory={parseHistory(input)} />);
    const before = [...container.querySelectorAll('.macro-history-anchor text')].map((p) => p.textContent);
    expect(before).toEqual(['A', 'B', 'C', 'D']);
    fireEvent.change(screen.getByRole('combobox', { name: 'Anchor B' }), {
      target: { value: screen.getByRole('combobox', { name: 'Anchor A' }).value },
    });
    expect(screen.getByRole('status')).toHaveTextContent('Anchor dates must follow');
    expect([...container.querySelectorAll('.macro-history-anchor text')].map((p) => p.textContent)).toEqual(before);
    fireEvent.click(screen.getByRole('checkbox', { name: 'Show historical A–D' }));
    expect(container.querySelectorAll('.macro-history-anchor')).toHaveLength(0);
  });

  it('keeps macro projection opt-in, separate from next-run references, and withholds it during replay', () => {
    const { container } = renderWithTools(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const history = container.querySelector('.macro-chart-history').getAttribute('points');
    expect(screen.getByRole('heading', { name: 'Nearby references for the current move' })).toBeVisible();
    const future = screen.getByRole('checkbox', { name: 'Show long-range macro scenario' });
    expect(future).not.toBeChecked();
    expect(container.querySelector('.macro-chart-future')).not.toBeInTheDocument();
    fireEvent.click(future);
    expect(container.querySelector('.macro-chart-future text')).toHaveTextContent('E?');
    expect(screen.getByText('SCENARIO · NO DATE')).toBeVisible();
    const y = container.querySelector('.macro-chart-future circle').getAttribute('cy');
    fireEvent.change(screen.getByRole('combobox', { name: 'Future reference level' }), { target: { value: '1.618' } });
    expect(container.querySelector('.macro-chart-future circle').getAttribute('cy')).not.toBe(y);
    expect(container.querySelector('.macro-chart-history').getAttribute('points')).not.toBeNull();
    fireEvent.click(future);
    expect(container.querySelector('.macro-chart-future')).not.toBeInTheDocument();
    expect(container.querySelector('.macro-chart-history').getAttribute('points')).toBe(history);
    fireEvent.click(future);
    fireEvent.change(screen.getByRole('slider', { name: 'Visible candles' }), { target: { value: '20' } });
    fireEvent.click(screen.getByRole('button', { name: 'Earlier', exact: true }));
    expect(container.querySelector('.macro-chart-future')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Later', exact: true }));
    expect(container.querySelector('.macro-chart-future')).toBeInTheDocument();
    fireEvent.input(screen.getByLabelText('Replay through (UTC)'), { target: { value: '2024-01-14' } });
    expect(screen.getByRole('checkbox', { name: 'Show long-range macro scenario' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Show long-range macro scenario' })).toBeDisabled();
    expect(container.querySelector('.macro-chart-future')).not.toBeInTheDocument();
  });

  it('loads real-data-shaped files locally and retains the last good chart on invalid import', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<MacroChartPage />);
    fireEvent.click(screen.getByText('Advanced: use a saved history file', { selector: 'summary' }));
    const input = screen.getByLabelText('Load price history');
    fireEvent.change(input, { target: { files: [{ size: 5000, text: async () => JSON.stringify(syntheticHistory()) }] } });
    await waitFor(() => expect(screen.getByText('TEST history loaded')).toBeVisible());
    expect(screen.queryByLabelText('Load price history')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Replace price history'), { target: { files: [{ size: 5, text: async () => '{bad' }] } });
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('not valid JSON'));
    expect(screen.getByText('TEST history loaded')).toBeVisible();
    expect(screen.getByRole('img')).toBeVisible();
    fireEvent.click(screen.getByText('Advanced: use a saved history file', { selector: 'summary' }));
    expect(screen.getByLabelText('Replace price history')).not.toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('not valid JSON');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('ignores an earlier import that finishes after a later selection', async () => {
    let finish;
    render(<MacroChartPage />);
    fireEvent.click(screen.getByText('Advanced: use a saved history file', { selector: 'summary' }));
    const input = screen.getByLabelText('Load price history');
    fireEvent.change(input, { target: { files: [{ size: 100, text: () => new Promise((resolve) => { finish = resolve; }) }] } });
    // A direct change can arrive even while the first input is disabled.
    const next = syntheticHistory(); next.instrument.symbol = 'NEXT'; next.instrument.product_id = 'NEXT-USD';
    fireEvent.change(input, { target: { files: [{ size: 100, text: async () => JSON.stringify(next) }] } });
    await waitFor(() => expect(screen.getByText('NEXT history loaded')).toBeVisible());
    finish(JSON.stringify(syntheticHistory()));
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
    expect(screen.getByText('NEXT history loaded')).toBeVisible();
  });

  it('offers a keyboard-readable candle inspection surface', () => {
    renderWithTools(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const chart = screen.getByRole('img');
    fireEvent.keyDown(chart, { key: 'Home' });
    expect(screen.getByText('2024-01-01', { selector: 'figcaption strong' })).toBeVisible();
    fireEvent.keyDown(chart, { key: 'ArrowRight' });
    expect(screen.getByText('2024-01-08', { selector: 'figcaption strong' })).toBeVisible();
  });

  it('renders a named unavailable state when replay has no completed weeks', () => {
    renderWithTools(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    fireEvent.change(screen.getByLabelText('Replay through (UTC)'), { target: { value: '2024-01-02' } });
    expect(screen.getByRole('heading', { name: 'No completed candles in this view' })).toBeVisible();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});
