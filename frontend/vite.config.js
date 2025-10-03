import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Ensure .js files with JSX parse correctly in dev and during dep scan
  esbuild: {
    jsx: 'automatic',
  },
  optimizeDeps: {
    esbuildOptions: {
      loader: {
        '.js': 'jsx',
      },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 3100,
    strictPort: true,
    proxy: {
      // SSE: route events to the local Worker (Durable Object) dev server
      '/api/events': {
        target: 'http://127.0.0.1:8787',
        changeOrigin: true,
      },
      // Everything else under /api goes to the Flask backend
      '/api': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
        bypass(req) {
          // Let the explicit /api/events rule handle SSE
          if (req.url && req.url.startsWith('/api/events')) return true;
        }
      },
      '/ws': {
        target: 'ws://127.0.0.1:5001',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 3100,
    strictPort: true,
  },
});
