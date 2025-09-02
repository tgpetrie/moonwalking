import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';

// Define spies in an object to avoid temporal dead zone in mock factory
const spies = { connect: vi.fn() };
vi.mock('../services/websocket.js', () => ({
  default: { getStatus: () => 'mock', send: vi.fn() },
  connectWebSocket: (...args) => spies.connect(...args),
  disconnectWebSocket: vi.fn(),
  subscribeToWebSocket: () => () => {}
}));

// Mock api fetch to avoid network
vi.mock('../api.js', () => ({
  API_ENDPOINTS: { gainersTable1Min: '/api/gainers' },
  fetchData: vi.fn().mockResolvedValue({ data: [] })
}));

import { WebSocketProvider } from './websocketcontext.jsx';

describe('WebSocketProvider polling fallback', () => {
  beforeEach(() => {
    spies.connect.mockClear();
  });

  it('does not attempt WebSocket connect when disabled by env default', async () => {
    render(<WebSocketProvider><div /></WebSocketProvider>);
    await new Promise(r => setTimeout(r, 50));
  expect(spies.connect).not.toHaveBeenCalled();
  });
});
