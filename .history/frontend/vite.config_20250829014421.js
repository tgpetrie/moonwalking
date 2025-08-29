import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'

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
                    tables: ['./src/components/GainersTable.jsx','./src/components/LosersTable.jsx','./src/components/GainersTable1Min.jsx'],
                    banners: ['./src/components/TopBannerScroll.jsx','./src/components/BottomBannerScroll.jsx'],
                    watchlist: ['./src/components/Watchlist.jsx','./src/components/WatchlistInsightsPanel.jsx']
                }
            }
        }
    },
    server: { 
        port: 5173,
        strictPort: true,
        hmr: {
            port: 5173
        },
        proxy: {
            // Forward /api calls to backend during development to avoid CORS
            '/api': {
                target: 'http://localhost:5001',
                changeOrigin: true,
                secure: false,
                rewrite: (path) => path
            }
        }
    },
    preview: { port: 5173 }
})
