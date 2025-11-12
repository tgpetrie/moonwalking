import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'

const backendPort = process.env.BACKEND_PORT || '5001'
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
                // Commented out manualChunks entries that pointed to legacy or moved files
                // so Rollup/Vite doesn't fail trying to resolve them. If you prefer
                // to keep manualChunks, re-add the entries but ensure the paths exist
                // under ./src or adjust to the new locations.
                manualChunks: {
                    react: ['react','react-dom'],
                    // tables: ['./src/components/GainersTable.jsx','./src/components/LosersTable.jsx','./src/components/GainersTable1Min.jsx'],
                    // banners: ['./src/components/TopBannerScroll.jsx','./src/components/BottomBannerScroll.jsx'],
                    // watchlist: ['./src/components/Watchlist.jsx','./src/components/WatchlistInsightsPanel.jsx']
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
            '/data': {
                target: `http://127.0.0.1:${backendPort}`,
                changeOrigin: true,
            },
            '/api': {
                target: `http://127.0.0.1:${backendPort}`,
                changeOrigin: true,
            },
            // '/sentiment': `http://127.0.0.1:${backendPort}`,
        }
    },
    preview: { port: vitePort }
})
