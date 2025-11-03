import { defineConfig } from 'vitest/config';

// Minimal Vitest config for integration runs. Integration runs should be invoked
// with VITE_API_URL and VITE_ENABLE_WS exported so the app will use a live backend.
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    // Allow longer timeouts for integration tests that may wait for real backends
    testTimeout: 30_000,
    hookTimeout: 30_000,
    // Do not load the project's .env.test automatically for integration runs
    // (invoker should set VITE_API_URL / VITE_ENABLE_WS explicitly)
  },
});
