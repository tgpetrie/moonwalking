import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Keep previous env resolution but do not auto-proxy everything during dev.
  const env = loadEnv(mode, process.cwd(), '')
  const API_BASE = env.VITE_API_ORIGIN || env.VITE_API_URL || 'http://127.0.0.1:5001'

  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: 5174,
      strictPort: true,
      proxy: {
        // Intentionally empty. Re-add only safe, explicit proxies when needed.
      }
    }
  }
})
