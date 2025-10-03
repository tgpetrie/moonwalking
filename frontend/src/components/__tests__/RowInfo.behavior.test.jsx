import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import GainersTable1Min from '../GainersTable1Min.jsx';
import { WatchlistProvider } from '../../hooks/useWatchlist.jsx';

const sample = [{
  symbol: 'ABC',
  product_id: 'ABC-USD',
  current_price: 1.23,
  price_change_percentage_1min: 2.1,
  volume_24h: 1000,
  high_24h: 1.5,
  low_24h: 1.0,
  rank: 1,
}];

describe('Row + Info behaviors', () => {
  it('Info opens panel; icon colored by sentiment', async () => {
    const onSelectCoin = vi.fn();
    render(
      <WatchlistProvider>
        <GainersTable1Min rows={sample} onSelectCoin={onSelectCoin} />
      </WatchlistProvider>
    );
    const infoBtn = await screen.findByRole('button', { name: /open sentiment panel/i });
    fireEvent.click(infoBtn);
    expect(onSelectCoin).toHaveBeenCalledTimes(1);
  const icon = infoBtn.querySelector('svg');
  // For SVG elements in jsdom, className is an object (SVGAnimatedString).
  // Use getAttribute('class') to read the class string reliably.
  const classAttr = icon?.getAttribute('class');
  expect(classAttr).toMatch(/text-bhabit-blue/);
  });
});
