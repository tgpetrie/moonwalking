import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import GainersTable1Min from '../GainersTable1Min.clean.jsx';
import { WatchlistProvider } from '../../hooks/useWatchlist.jsx';

// Minimal row fixture
const rows = [
  { symbol: 'BTC-USD', current_price: 62000, change: 1.2, rank: 1, initial_price_1min: 61200 },
];

describe('GainersTable1Min seeded badge', () => {
  it('renders seeded badge when seeded prop is true and DEV environment', () => {
    // Vitest sets import.meta.env.DEV=true by default in test environment
    render(
      <WatchlistProvider>
        <GainersTable1Min rows={rows} seeded={true} loading={false} error={null} />
      </WatchlistProvider>
    );
    const badge = screen.getByText(/seeded \(dev\)/i);
    expect(badge).toBeInTheDocument();
  });
});
