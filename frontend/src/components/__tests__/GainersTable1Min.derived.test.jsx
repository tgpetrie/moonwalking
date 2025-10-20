import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import GainersTable1Min from '../GainersTable1Min.clean.jsx';
import { WatchlistProvider } from '../../hooks/useWatchlist.jsx';

describe('GainersTable1Min derived/allowEmpty behavior', () => {
  it('does not show ErrorBanner when allowEmpty is true (dev seeded/derived)', () => {
    render(
      <WatchlistProvider>
        <GainersTable1Min rows={[]} seeded={false} allowEmpty={true} loading={false} error={null} />
      </WatchlistProvider>
    );
    // ErrorBanner text contains "Failed to load" when present
    const maybe = screen.queryByText(/Failed to load/i);
    expect(maybe).toBeNull();
  });

  it('shows ErrorBanner when allowEmpty is false and rows empty', () => {
    render(
      <WatchlistProvider>
        <GainersTable1Min rows={[]} seeded={false} allowEmpty={false} loading={false} error={null} />
      </WatchlistProvider>
    );
    const banner = screen.getByText(/Failed to load/i);
    expect(banner).toBeInTheDocument();
  });
});
