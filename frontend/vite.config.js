import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'

// PROXY-FIRST ARCHITECTURE: Single canonical backend
// Vite dev proxy forwards /data and /api to Flask backend on port 5003
const target = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:5003'

const vitePort = Number(process.env.VITE_PORT || 5173)

export default defineConfig({
  plugins: [
    react(),
    visualizer({ filename: 'dist/stats.html', gzipSize: true, brotliSize: true, template: 'treemap', emitFile: true })
  ],
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react','react-dom'],
        }
      }
    }
  },
  server: {
    host: '127.0.0.1',
    port: vitePort,
    strictPort: true,
    hmr: {
      host: '127.0.0.1',
      port: vitePort,
      protocol: 'ws'
    },
    proxy: {
      '/data': { target, changeOrigin: true },
      '/api': { target, changeOrigin: true },
      // Keep legacy sentiment paths working, but route through the main backend proxy target.
      '/api/sentiment': { target, changeOrigin: true },
      '/sentiment': { target, changeOrigin: true },
    }
  },
  preview: { port: vitePort }
})
