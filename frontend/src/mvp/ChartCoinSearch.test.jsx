import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import MacroChartPage from './MacroChartPage.jsx';
import { parseHistory } from '../utils/macroChart.js';
import { syntheticHistory } from '../test/macroHistory.test.fixture.js';

afterEach(cleanup);
const match = { id: 'AMP-USD', symbol: 'AMP', venue: 'Coinbase', quote: 'USD', status: 'online' };
function ampFixture() {
  const source = syntheticHistory(); source.instrument.symbol = 'AMP'; source.instrument.product_id = 'AMP-USD';
  return parseHistory(source); // Synthetic test prices, not AMP market observations.
}
async function search() {
  fireEvent.change(screen.getByLabelText('Search coin'), { target: { value: 'AMP' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search', exact: true }));
  await screen.findByRole('button', { name: /Analyse AMP/ });
}
describe('coin-to-chart workflow', () => {
  it('recognizes a completed close above the previous historical high without moving that comparison to the new candle', () => {
    const source = syntheticHistory();
    source.candles.slice(-7).forEach((row) => { for (const key of ['open', 'high', 'low', 'close']) row[key] += 20; });
    render(<MacroChartPage initialHistory={parseHistory(source)} />);
    expect(screen.getByText(/last completed close is already above/)).toBeVisible();
    expect(screen.getByText(/Old recovery ratios still describe their original historical range/)).toBeVisible();
  });
  it('loads and explains a selected coin without any file or manual anchors', async () => {
    const client = { search: vi.fn(async () => [match]), history: vi.fn(async () => ampFixture()) };
    const { container } = render(<MacroChartPage historyClient={client} />);
    expect(screen.getByLabelText('Load price history')).not.toBeVisible();
    await search();
    fireEvent.click(screen.getByRole('button', { name: /Analyse AMP/ }));
    await screen.findByText('AMP history loaded');
    expect(client.history.mock.calls[0][0]).toBe('AMP-USD');
    expect(screen.getByRole('heading', { name: 'Focus on the next recovery' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Nearby references for the current move' })).toBeVisible();
    expect(screen.getByLabelText('Macro high')).not.toBeVisible();
    expect(container.querySelector('.next-run-baseline')).toHaveTextContent('Daily close');
    expect(container.querySelector('.macro-chart-recovery')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Show long-range macro band' }));
    expect(container.querySelector('.macro-chart-recovery text')).toHaveTextContent('50%');
    fireEvent.click(screen.getByRole('checkbox', { name: 'Show smaller a–d' }));
    expect(container.querySelectorAll('.macro-nested-label')).toHaveLength(4);
    const future = screen.getByRole('checkbox', { name: 'Show long-range macro scenario' });
    expect(future).not.toBeChecked();
    fireEvent.click(future);
    fireEvent.change(screen.getByRole('combobox', { name: 'Future reference level' }), { target: { value: '1.618' } });
    expect(container.querySelector('.macro-chart-future')).toBeInTheDocument();
    expect(screen.getByText(/would not establish a return to the old cycle peak/)).toBeVisible();
  });
  it('keeps the current chart on a failed download and explains unsupported searches', async () => {
    const client = { search: vi.fn(async () => [match]), history: vi.fn(async () => { throw new Error('Provider unavailable'); }) };
    render(<MacroChartPage historyClient={client} initialHistory={parseHistory(syntheticHistory())} />);
    await search(); fireEvent.click(screen.getByRole('button', { name: /Analyse AMP/ }));
    await screen.findByRole('alert');
    expect(screen.getByText('TEST history loaded')).toBeVisible();
    expect(screen.getByRole('alert')).toHaveTextContent('previous chart has been kept');
    client.search.mockResolvedValue([]);
    fireEvent.change(screen.getByLabelText('Search coin'), { target: { value: 'UNKNOWN' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search', exact: true }));
    await screen.findByText(/No matching USD market/);
    expect(screen.getByText('TEST history loaded')).toBeVisible();
  });
  it('cancels an in-flight download and ignores a late response', async () => {
    let finish;
    const client = { search: vi.fn(async () => [match]), history: vi.fn(() => new Promise((resolve) => { finish = resolve; })) };
    render(<MacroChartPage historyClient={client} />);
    await search(); fireEvent.click(screen.getByRole('button', { name: /Analyse AMP/ }));
    await screen.findByRole('button', { name: 'Cancel', exact: true });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel', exact: true }));
    finish(ampFixture());
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
    expect(screen.queryByText('AMP history loaded')).not.toBeInTheDocument();
    expect(client.history.mock.calls[0][1].signal.aborted).toBe(true);
  });
});
