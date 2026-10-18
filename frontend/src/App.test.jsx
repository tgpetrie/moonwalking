import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App.jsx';

const { sentimentMounted } = vi.hoisted(() => ({ sentimentMounted: vi.fn() }));
vi.mock('./context/SentimentContext.jsx', () => ({
  SentimentProvider: ({ children }) => { sentimentMounted(); return children; },
}));
vi.mock('./context/WatchlistContext.jsx', () => ({ WatchlistProvider: ({ children }) => children, useWatchlist: () => ({ items: [] }) }));
vi.mock('./context/IntelligenceContext.jsx', () => ({ IntelligenceProvider: ({ children }) => children }));
vi.mock('./context/DataContext.jsx', () => ({ DataProvider: ({ children }) => children }));
vi.mock('./components/DashboardShell.jsx', () => ({ default: () => <p>Legacy board</p> }));
vi.mock('./mvp/MvpApp.jsx', () => ({ default: () => <p>Product shell</p> }));
vi.mock('./mvp/MacroChartPage.jsx', () => ({ default: () => <p>Local chart workspace</p> }));

afterEach(() => { cleanup(); sentimentMounted.mockClear(); window.history.replaceState({}, '', '/'); });

describe('route provider isolation', () => {
  it('opens the chart without mounting the market-polling sentiment provider', async () => {
    window.history.replaceState({}, '', '/chart-map');
    render(<App />);
    expect(await screen.findByText('Local chart workspace')).toBeVisible();
    expect(sentimentMounted).not.toHaveBeenCalled();
  });
  it.each([['/', 'Legacy board'], ['/design-system', 'Product shell']])('retains the shared provider on %s', (route, content) => {
    window.history.replaceState({}, '', route);
    render(<App />);
    expect(screen.getByText(content)).toBeVisible();
    expect(sentimentMounted).toHaveBeenCalled();
  });
});
