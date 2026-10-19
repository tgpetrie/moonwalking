import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { syntheticHistory } from '../test/macroHistory.test.fixture.js';
import { parseHistory } from '../utils/macroChart.js';
import MacroChartPage from './MacroChartPage.jsx';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('local long-term chart workspace', () => {
  it('starts with an honest empty state and makes no API requests', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<MacroChartPage />);
    expect(screen.getByRole('heading', { name: 'Build a map from real price history' })).toBeVisible();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('plots completed weekly candles and exposes data coverage and scenario limits', () => {
    const { container } = render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    expect(container.querySelectorAll('.macro-candle')).toHaveLength(30);
    expect(screen.getByText('Low in analysed history')).toBeVisible();
    expect(screen.getByText('High in analysed history')).toBeVisible();
    expect(screen.getByText('Future timing is not estimated')).toBeVisible();
    expect(screen.getByText(/A full Elliott Wave count has not been established/)).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Anchor A' }).value).toMatch(/^low-/);
    expect(screen.getByText('Conditional scenario')).toBeVisible();
  });

  it('changes timeframe and withholds future candles and anchors during replay', () => {
    const { container } = render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    fireEvent.click(screen.getByRole('button', { name: 'Daily', exact: true }));
    expect(container.querySelectorAll('.macro-candle')).toHaveLength(160);
    fireEvent.input(screen.getByLabelText('Replay through (UTC)'), { target: { value: '2024-01-14' } });
    expect(container.querySelectorAll('.macro-candle')).toHaveLength(14);
    expect(screen.getByRole('combobox', { name: 'Anchor C' })).toHaveValue('');
    expect(screen.queryByText('Conditional scenario')).not.toBeInTheDocument();
  });

  it('rejects incompatible anchor ordering while retaining the historical chart', () => {
    render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const a = screen.getByRole('combobox', { name: 'Anchor A' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Anchor B' }), { target: { value: a.value } });
    expect(screen.getByRole('status')).toHaveTextContent('Anchor dates must follow A, then B, then C.');
    expect(screen.getByRole('img')).toBeVisible();
  });

  it('changes the display scale without changing the selected anchors or level prices', () => {
    const { container } = render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
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
    const { container } = render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
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
    const { container } = render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const toggle = screen.getByRole('checkbox', { name: 'Show macro band' });
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

  it('loads real-data-shaped files locally and retains the last good chart on invalid import', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<MacroChartPage />);
    const input = screen.getByLabelText('Load price history');
    fireEvent.change(input, { target: { files: [{ size: 5000, text: async () => JSON.stringify(syntheticHistory()) }] } });
    await waitFor(() => expect(screen.getByText('TEST history loaded')).toBeVisible());
    fireEvent.change(input, { target: { files: [{ size: 5, text: async () => '{bad' }] } });
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('not valid JSON'));
    expect(screen.getByText('TEST history loaded')).toBeVisible();
    expect(screen.getByRole('img')).toBeVisible();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('ignores an earlier import that finishes after a later selection', async () => {
    let finish;
    render(<MacroChartPage />);
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
    render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const chart = screen.getByRole('img');
    fireEvent.keyDown(chart, { key: 'Home' });
    expect(screen.getByText('2024-01-01', { selector: 'figcaption strong' })).toBeVisible();
    fireEvent.keyDown(chart, { key: 'ArrowRight' });
    expect(screen.getByText('2024-01-08', { selector: 'figcaption strong' })).toBeVisible();
  });

  it('renders a named unavailable state when replay has no completed weeks', () => {
    render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    fireEvent.change(screen.getByLabelText('Replay through (UTC)'), { target: { value: '2024-01-02' } });
    expect(screen.getByRole('heading', { name: 'No completed candles in this view' })).toBeVisible();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});
