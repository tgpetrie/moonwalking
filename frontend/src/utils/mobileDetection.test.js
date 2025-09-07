import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  isMobileDevice,
  isIOS,
  isAndroid,
  isSafari,
  getMobileOptimizedConfig,
  addVisibilityChangeListener,
  addNetworkChangeListener
} from './mobileDetection.js';

// Helper to override navigator.userAgent
const setUserAgent = (ua) => {
  Object.defineProperty(window.navigator, 'userAgent', { value: ua, configurable: true });
};

describe('mobileDetection utilities', () => {
  beforeEach(() => {
    // Default desktop baseline
    setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36');
    // reset width
    Object.defineProperty(window, 'innerWidth', { value: 1200, configurable: true });
    // reset touch capability
    try { Object.defineProperty(navigator, 'maxTouchPoints', { value: 0, configurable: true }); } catch (_) {}
  });

  it('detects mobile by user agent', () => {
    setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)');
    expect(isMobileDevice()).toBe(true);
  });

  it('detects mobile by small screen width fallback when touch-capable', () => {
    Object.defineProperty(window, 'innerWidth', { value: 500, configurable: true });
    try { Object.defineProperty(navigator, 'maxTouchPoints', { value: 5, configurable: true }); } catch (_) {}
    expect(isMobileDevice()).toBe(true);
  });

  it('identifies iOS, Android, Safari correctly', () => {
    setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) Safari/604.1');
    expect(isIOS()).toBe(true);
    expect(isAndroid()).toBe(false);
    expect(isSafari()).toBe(true);
    setUserAgent('Mozilla/5.0 (Linux; Android 10) Chrome/110 Mobile Safari/537.36');
    expect(isAndroid()).toBe(true);
    expect(isIOS()).toBe(false);
    // Chrome on Android should not be detected as Safari by our regex
    expect(isSafari()).toBe(false);
  });

  it('returns different configs for mobile vs desktop', () => {
    // Desktop baseline
    let cfgDesktop = getMobileOptimizedConfig();
    expect(cfgDesktop.fetchTimeout).toBe(5000);
    // Force mobile via UA
    setUserAgent('Mozilla/5.0 (Android 12; Mobile)');
    let cfgMobile = getMobileOptimizedConfig();
    expect(cfgMobile.fetchTimeout).toBe(8000);
    expect(cfgMobile.fetchTimeout).not.toBe(cfgDesktop.fetchTimeout);
  });

  it('visibility change listener invokes callback with correct foreground state', () => {
    const cb = vi.fn();
    const cleanup = addVisibilityChangeListener(cb);
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    cleanup();
    expect(cb).toHaveBeenCalledTimes(2);
    expect(cb.mock.calls[0][0]).toBe(false); // hidden -> foreground false
    expect(cb.mock.calls[1][0]).toBe(true);  // visible -> true
  });

  it('network change listener (API available) responds to change events', () => {
    const mockConnection = {
      effectiveType: '4g',
      downlink: 10,
      rtt: 50,
      addEventListener: vi.fn((evt, handler) => { mockConnection._handler = handler; }),
      removeEventListener: vi.fn()
    };
    Object.defineProperty(navigator, 'connection', { value: mockConnection, configurable: true });
    const cb = vi.fn();
    const cleanup = addNetworkChangeListener(cb);
    // simulate event
    mockConnection._handler();
    cleanup();
    expect(cb).toHaveBeenCalledWith({ effectiveType: '4g', downlink: 10, rtt: 50 });
    expect(mockConnection.removeEventListener).toHaveBeenCalled();
  });

  it('network change listener fallback returns cleanup function without throwing', () => {
    // Remove any connection prop entirely to trigger fallback path
    // Some jsdom versions keep it non-configurable; guard with try
    try { delete navigator.connection; } catch (e) {
      Object.defineProperty(navigator, 'connection', { value: undefined, configurable: true });
    }
    const cleanup = addNetworkChangeListener(() => {});
    expect(typeof cleanup).toBe('function');
    cleanup();
  });
});
