import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import OneMinGainersColumns from '../OneMinGainersColumns.jsx';
import WebSocketContext from '../../context/websocketcontext.jsx';
import { WatchlistProvider } from '../../hooks/useWatchlist.jsx';

// Provide a deterministic latestData via mocking the WebSocketContext value
const fixture = {
  gainersTop20: [
    { symbol: 'A-USD', rank: 1 },
    { symbol: 'B-USD', rank: 2 },
    { symbol: 'C-USD', rank: 3 },
    { symbol: 'D-USD', rank: 4 },
    { symbol: 'E-USD', rank: 5 },
    { symbol: 'F-USD', rank: 6 },
    { symbol: 'G-USD', rank: 7 },
    { symbol: 'H-USD', rank: 8 },
  ],
  latestData: { raw: null },
};

it('produces disjoint left/right sets when rendering both columns', () => {
  const { container } = render(
    <WebSocketContext.Provider value={{
      gainersTop20: fixture.gainersTop20,
      latestData: fixture.latestData,
    }}>
      <WatchlistProvider>
        <OneMinGainersColumns />
      </WatchlistProvider>
    </WebSocketContext.Provider>
  );

  // Each row renders a symbol inside an element with the font-headline class
  const symbolEls = Array.from(container.querySelectorAll('.font-headline'));
  const texts = symbolEls.map((el) => el.textContent.trim()).filter(Boolean);
  const set = new Set(texts);
  expect(set.size).toBe(texts.length); // no repeated symbol text
});
