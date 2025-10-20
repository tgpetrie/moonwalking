import React from 'react';
import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render } from '@testing-library/react';
import { WebSocketProvider } from './websocketcontext.jsx';

// Spies must exist before mock factory executes
const spies = { connect: vi.fn() };

vi.mock('../services/websocket.js', () => ({
  default: { getStatus: () => 'mock', send: vi.fn() },
  connectWebSocket: (...args) => spies.connect(...args),
  disconnectWebSocket: vi.fn(),
  subscribeToWebSocket: () => () => {}
}));

vi.mock('../api.js', () => ({
  API_ENDPOINTS: { gainersTable1Min: '/api/gainers' },
  fetchData: vi.fn().mockResolvedValue({ data: [] })
}));

beforeAll(() => {
  vi.stubGlobal('setTimeout', (fn) => { fn(); return 1; });
});

beforeAll(() => {
  window.importMeta = window.importMeta || {};
  window.importMeta.env = window.importMeta.env || {};
  window.importMeta.env.VITE_DISABLE_WS = 'true';
});

describe('WebSocketProvider polling fallback', () => {
  beforeEach(() => spies.connect.mockClear());
  it('does not attempt WebSocket connect when disabled by env default', () => {
    const noopScheduler = () => 1;
    render(<WebSocketProvider pollingScheduler={noopScheduler}><div /></WebSocketProvider>);
    expect(spies.connect).not.toHaveBeenCalled();
  });
});
