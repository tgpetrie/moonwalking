import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ChartTimingPanel from './ChartTimingPanel.jsx';
import MacroChartPage from './MacroChartPage.jsx';
import { DAY, parseHistory } from '../utils/macroChart.js';
import { syntheticHistory } from '../test/macroHistory.test.fixture.js';

afterEach(cleanup);
// Synthetic fixture only.
const p = { time: 0, price: 100, confirmed_at: DAY, type: 'high', label: 'Recent high' };
const props = { macroAnchors: [], recentAnchors: [], levels: [p], currency: 'USD', asOf: 3 * DAY,
  dailyCandles: [{ time: DAY, end: 2 * DAY, low: 99, high: 102, close: 100 },
    { time: 2 * DAY, end: 3 * DAY, low: 90, high: 95, close: 92 }] };

describe('timing context and chart navigation', () => {
  it('shows dated observations and a future review checkpoint without an arrival forecast', () => {
    const focus = vi.fn();
    render(<ChartTimingPanel {...props} onFocus={focus} />);
    expect(screen.getByText(/Seven-day review checkpoint: 1970-01-10/)).toBeVisible();
    expect(screen.getByText(/checkpoint is after this replay cutoff/)).toBeVisible();
    expect(screen.getByText(/Future arrival window: not estimated/)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'View touch 1970-01-02' }));
    expect(focus).toHaveBeenCalledWith(DAY, DAY);
    fireEvent.change(screen.getByRole('combobox', { name: 'Near-level inspection width' }), { target: { value: '2' } });
    expect(screen.getByText(/Watch \$98.00–\$102.00/)).toBeVisible();
  });
  it('focuses a recent period in the daily chart without changing the replay cutoff', () => {
    const { container } = render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const cutoff = screen.getByLabelText('Replay through (UTC)').value;
    const reading = container.querySelector('.macro-reading').textContent;
    const first = screen.getByRole('button', { name: 'View a–b', exact: true });
    fireEvent.click(first);
    expect(screen.getByRole('button', { name: 'Weekly', exact: true })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByLabelText('Replay through (UTC)')).toHaveValue(cutoff);
    expect(container.querySelector('.macro-focus-note')).toHaveTextContent('Replay cutoff unchanged');
    expect(container.querySelectorAll('.macro-candle').length).toBeLessThan(160);
    expect(container.querySelector('.macro-reading').textContent).toBe(reading);
    expect(container.querySelector('.macro-chart-recovery')).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Show future scenario' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Fit history', exact: true }));
    expect(container.querySelector('.macro-focus-note')).not.toBeInTheDocument();
    expect(container.querySelectorAll('.macro-candle')).toHaveLength(30);
    fireEvent.click(screen.getByRole('button', { name: 'View a–b', exact: true }));
    fireEvent.click(screen.getByRole('button', { name: 'Weekly', exact: true }));
    expect(container.querySelector('.macro-focus-note')).not.toBeInTheDocument();
    expect(container.querySelectorAll('.macro-candle')).toHaveLength(30);
  });
});
