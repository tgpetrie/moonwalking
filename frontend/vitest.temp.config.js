import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.js'],
    globals: true,
    include: ['src/lib/sentiment.test.js', 'src/components/__tests__/RowInfo.behavior.test.jsx'],
    exclude: ['node_modules', 'dist'],
  },
});
