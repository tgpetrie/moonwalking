import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.js'],
    globals: true,
    include: ['src/utils/**/*.{test,spec}.js', 'src/context/**/*.{test,spec}.jsx', 'src/context/websocketcontext.test.jsx', 'src/context/websocketcontext.polling.test.jsx'],
    exclude: ['node_modules','dist'],
    coverage: {
      reporter: ['text','html'],
      include: ['src/utils/**/*.js', 'src/context/**/*.jsx'],
      exclude: ['src/context/websocketcontext.polling.test.jsx'],
      thresholds: {
        lines: 30,
        functions: 30,
        branches: 25,
        statements: 30
      }
    }
  }
});