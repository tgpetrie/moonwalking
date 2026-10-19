import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { DAY, parseHistory } from '../utils/macroChart.js';
import { syntheticHistory } from '../test/macroHistory.test.fixture.js';
import MacroChartPage from './MacroChartPage.jsx';
import { distanceText } from './ChartLevelGuide.jsx';

afterEach(cleanup);
describe('price reference explanations', () => {
  it('shows signed price distance, guards missing prices and never labels it probability', () => {
    expect(distanceText(20, 10)).toBe('+100.0% · above reference close');
    expect(distanceText(5, 10)).toBe('−50.0% · below reference close');
    expect(distanceText(10, 10)).toMatch(/^At the reference close/);
    expect(distanceText(10, 0)).toBe('Distance unavailable');
    expect(distanceText(Infinity, 10)).toBe('Distance unavailable');
  });
  it('explains anchors and calculations, highlights sources and retains original evidence during inspection', () => {
    const { container } = render(<MacroChartPage initialHistory={parseHistory(syntheticHistory())} />);
    const baseline = container.querySelector('.macro-guide-baseline').textContent;
    const cutoff = screen.getByLabelText('Replay through (UTC)').value;
    fireEvent.click(screen.getByRole('button', { name: 'Explain Historical C' }));
    const details = container.querySelector('#macro-level-explanation');
    expect(details).toHaveTextContent('Actual extreme');
    expect(details).toHaveTextContent('Candle begins');
    expect(details).toHaveTextContent('Confirmed');
    expect(container.querySelectorAll('.macro-evidence-candle')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Explain 61.8% recovery' }));
    expect(details).toHaveTextContent('Calculation:');
    expect(details).toHaveTextContent('0.618 ×');
    expect(screen.getByRole('combobox', { name: 'Future reference level' })).toHaveValue('0.618');
    expect(container.querySelectorAll('.macro-evidence-candle')).toHaveLength(2);
    const explanation = details.textContent;
    fireEvent.click(screen.getByRole('button', { name: 'View source candles' }));
    expect(screen.getByLabelText('Replay through (UTC)')).toHaveValue(cutoff);
    expect(screen.getByRole('button', { name: 'Weekly', exact: true })).toHaveAttribute('aria-pressed', 'true');
    expect(container.querySelector('.macro-guide-baseline').textContent).toBe(baseline);
    expect(details.textContent).toBe(explanation);
    expect(screen.getByRole('checkbox', { name: 'Show future scenario' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Fit history' }));
    expect(container.querySelectorAll('.macro-evidence-candle')).toHaveLength(2);
    // Replaying before either anchor existed must remove the old explanation.
    fireEvent.input(screen.getByLabelText('Replay through (UTC)'), { target: { value: '2024-01-14' } });
    expect(container.querySelector('#macro-level-explanation')).not.toHaveTextContent('0.618 ×');
    expect(screen.queryByRole('button', { name: 'Explain 61.8% recovery' })).not.toBeInTheDocument();
  });
  it('uses the weekly completed close even when daily data extends further', () => {
    const input = syntheticHistory();
    input.candles.push(...Array.from({ length: 2 }, (_, i) => ({ start: input.captured_at + i * DAY, end: input.captured_at + (i + 1) * DAY, open: 8, high: 9, low: 7, close: 8, volume: 10, complete: true })));
    input.captured_at += 2 * DAY;
    render(<MacroChartPage initialHistory={parseHistory(input)} />);
    expect(document.querySelector('.macro-guide-baseline')).toHaveTextContent('weekly');
    const weekly = document.querySelector('.macro-guide-baseline').textContent;
    fireEvent.click(screen.getByRole('button', { name: 'Daily', exact: true }));
    expect(document.querySelector('.macro-guide-baseline')).toHaveTextContent('daily');
    expect(document.querySelector('.macro-guide-baseline').textContent).not.toBe(weekly);
  });
});
