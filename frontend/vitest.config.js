import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.js'],
    globals: true,
      environmentOptions: {
        jsdom: {
          NODE_ENV: 'test', // This is the crucial line to add
        },
      },
    coverage: {
      reporter: ['text','html'],
      include: ['src/utils/**/*.js', 'src/context/**/*.jsx'],
      exclude: ['src/**/*.test.*', 'src/**/*.spec.*'],
      thresholds: {
        lines: 30,
        functions: 30,
        branches: 25,
        statements: 30
      }
    }
  }
});