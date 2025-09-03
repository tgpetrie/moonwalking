// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render } from '@testing-library/react';
// Do not import WebSocketProvider at module-eval time. We'll dynamically import it
// after mocks are in place so module initialization reads the mocked `flags`.
//
// NOTE: The provider reads `flags` from `../config.js` at module init. In tests
// we mock `../config.js` to control `VITE_DISABLE_WS`. Importing the provider
// after applying the mock guarantees the module sees the test-provided flags
// (otherwise import-time evaluation may read the real runtime env and make
// connect attempts before the mock is applied). This pattern is intentional —
// keep dynamic import here and prefer module-level mocks for other dependencies.

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

// Mock runtime flags so the provider sees WS disabled at import time
vi.mock('../config.js', () => ({
  flags: {
    VITE_DISABLE_WS: true,
    VITE_DEBUG_LOGS: false,
    VITE_ONE_MIN_WS_THROTTLE_MS: 15000
  }
}));

beforeAll(() => {
  vi.stubGlobal('setTimeout', (fn) => { fn(); return 1; });
});

beforeAll(() => {
  globalThis.importMeta = globalThis.importMeta || {};
  globalThis.importMeta.env = globalThis.importMeta.env || {};
  globalThis.importMeta.env.VITE_DISABLE_WS = 'true';
});

describe('WebSocketProvider polling fallback', () => {
  beforeEach(() => spies.connect.mockClear());
  it('does not attempt WebSocket connect when disabled by env default', async () => {
    const noopScheduler = () => 1;
    // Dynamically import after mocks so the module picks up mocked flags
    const { WebSocketProvider } = await import('./websocketcontext.jsx');
    render(<WebSocketProvider pollingScheduler={noopScheduler}><div /></WebSocketProvider>);
    expect(spies.connect).not.toHaveBeenCalled();
  });
});
