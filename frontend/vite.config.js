import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      // REST -> Flask backend (locked to 5001)
      "/api": {
        target: "http://127.0.0.1:5001",
        changeOrigin: true,
      },
      // WS -> bridge (locked to 5100)
      "/socket.io": {
        target: "http://127.0.0.1:5100",
        ws: true,
        changeOrigin: true,
      },
    },
  },
  plugins: [react()],
});
