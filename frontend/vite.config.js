import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'

const target = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:5001'
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
      '/data': { target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:5002', changeOrigin: true },
      '/api': { target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:5002', changeOrigin: true },
      '/api/sentiment': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/sentiment/, '/sentiment'),
      },
      '/sentiment': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        secure: false,
      },
    }
  },
  preview: { port: vitePort }
})
