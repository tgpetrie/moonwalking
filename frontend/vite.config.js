import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'

const target =
  process.env.VITE_PROXY_TARGET ||
  process.env.VITE_API_BASE_URL ||
  'http://127.0.0.1:5003'

const vitePort = Number(process.env.VITE_PORT || 5173)

const attachProxyErrorHandler = (proxy) => {
  proxy.on('error', (err, req, res) => {
    if (!res || res.headersSent) return
    res.writeHead(502, { 'Content-Type': 'application/json' })
    res.end(
      JSON.stringify({
        ok: false,
        error: 'backend_unreachable',
        detail: String(err?.message || err || 'proxy error'),
        path: req?.url || '',
      })
    )
  })
}

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
      '/data': { target, changeOrigin: true, configure: attachProxyErrorHandler },
      '/api': { target, changeOrigin: true, ws: true, configure: attachProxyErrorHandler },
      // Keep legacy sentiment paths working, but route through the main backend proxy target.
      '/api/sentiment': { target, changeOrigin: true, configure: attachProxyErrorHandler },
      '/sentiment': { target, changeOrigin: true, configure: attachProxyErrorHandler },
    }
  },
  preview: { port: vitePort }
})
