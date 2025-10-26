import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import GainersTable1Min from '../GainersTable1Min.clean.jsx';
import { WatchlistProvider } from '../../hooks/useWatchlist.jsx';

describe('GainersTable1Min derived/allowEmpty behavior', () => {
  it('does not show empty status note when allowEmpty is true (dev seeded/derived)', () => {
    render(
      <WatchlistProvider>
        <GainersTable1Min rows={[]} seeded={false} allowEmpty={true} loading={false} error={null} />
      </WatchlistProvider>
    );
    const maybe = screen.queryByText(/No 1-min data available/i);
    expect(maybe).toBeNull();
  });

  it('shows empty status note when allowEmpty is false and rows empty', () => {
    render(
      <WatchlistProvider>
        <GainersTable1Min rows={[]} seeded={false} allowEmpty={false} loading={false} error={null} />
      </WatchlistProvider>
    );
    const note = screen.getByText(/No 1-min data available/i);
    expect(note).toBeInTheDocument();
  });
});
