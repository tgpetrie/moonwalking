// scheduleIdle: cross-browser wrapper for requestIdleCallback with timeout fallback.

export function scheduleIdle(fn, { timeout = 1000 } = {}) {
  if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
    return window.requestIdleCallback(fn, { timeout });
  }
  return setTimeout(() => fn({ didTimeout: true, timeRemaining: () => 0 }), timeout);
}

export function cancelIdle(id) {
  if (typeof window !== 'undefined' && 'cancelIdleCallback' in window) {
    window.cancelIdleCallback(id);
  } else {
    clearTimeout(id);
  }
}