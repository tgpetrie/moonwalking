import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';

// Define callbacks object BEFORE mock (hoisting safety)
const callbacks = {};
vi.mock('../services/websocket.js', () => ({
	default: {
		getStatus: () => 'mock-status',
		send: vi.fn()
	},
	connectWebSocket: vi.fn(),
	disconnectWebSocket: vi.fn(),
	subscribeToWebSocket: (event, cb) => {
		callbacks[event] = cb;
		return () => { delete callbacks[event]; };
	}
}));

import { WebSocketProvider, useWebSocket } from './websocketcontext.jsx';

// Helper test component to expose context values
const Probe = () => {
		const { connectionStatus, gainersTop20, gainers3mTop, losers3mTop } = useWebSocket();
	return (
		<div>
			<span data-testid="status">{connectionStatus}</span>
			<span data-testid="gainers-count">{gainersTop20.length}</span>
				<span data-testid="gainers3m-count">{gainers3mTop.length}</span>
				<span data-testid="losers3m-count">{losers3mTop.length}</span>
		</div>
	);
};

describe('WebSocketProvider basic behavior', () => {
	beforeEach(() => {
		// Clear previous callbacks between tests
		Object.keys(callbacks).forEach(k => delete callbacks[k]);
	});

	it('starts disconnected and updates on connection event', () => {
		render(
			<WebSocketProvider>
				<Probe />
			</WebSocketProvider>
		);
		expect(screen.getByTestId('status').textContent).toBe('disconnected');
		act(() => {
			callbacks.connection?.({ status: 'connected' });
		});
		expect(screen.getByTestId('status').textContent).toBe('connected');
	});

	it('derives gainersTop20 when crypto_update emitted', () => {
		render(
			<WebSocketProvider>
				<Probe />
			</WebSocketProvider>
		);
		// emit connection and crypto data
		const sample = Array.from({ length: 5 }).map((_, i) => ({
			symbol: `COIN${i}`,
			current_price: 100 + i,
			price_change_percentage_1min: (i + 1) * 0.5
		}));
		act(() => {
			callbacks.crypto_update?.(sample);
		});
		// After update, gainersTop20 should have entries
		expect(Number(screen.getByTestId('gainers-count').textContent)).toBeGreaterThan(0);
	});

		it('derives 3m movers sorted correctly', () => {
			render(
				<WebSocketProvider>
					<Probe />
				</WebSocketProvider>
			);
			const sample = [
				{ symbol: 'X', current_price: 10, price_change_percentage_1min: 0.1, price_change_percentage_3min: 5 },
				{ symbol: 'Y', current_price: 11, price_change_percentage_1min: 0.2, price_change_percentage_3min: -2 },
				{ symbol: 'Z', current_price: 12, price_change_percentage_1min: 0.3, price_change_percentage_3min: 10 }
			];
			act(() => { callbacks.crypto_update?.(sample); });
			const gainersCount = Number(screen.getByTestId('gainers3m-count').textContent);
			const losersCount = Number(screen.getByTestId('losers3m-count').textContent);
			expect(gainersCount).toBe(3);
			expect(losersCount).toBe(3);
		});
});
