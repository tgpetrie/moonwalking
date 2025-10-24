import express from 'express';
import 'dotenv/config';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createProxyMiddleware } from 'http-proxy-middleware';
import handler from './api/ask-codex.js';
import { loadConfig } from './config.js';
import { logger, reqIdMiddleware } from './logger.js';

// ----------------------------------------------------------------------------
// App + config
// ----------------------------------------------------------------------------
const cfg = loadConfig();
const app = express();
app.use(express.json({ limit: '2mb' }));
app.use(reqIdMiddleware);

// ----------------------------------------------------------------------------
// Paths
// ----------------------------------------------------------------------------
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIST = path.join(__dirname, 'frontend', 'dist');

// ----------------------------------------------------------------------------
// API routes (local handlers)
// ----------------------------------------------------------------------------
app.post('/api/ask-codex', (req, res) => handler(req, res));
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', uptime: process.uptime(), commit: process.env.GIT_COMMIT || null });
});

// ----------------------------------------------------------------------------
// Backend API proxy (Flask) for all /api/* except /api/ask-codex
// ----------------------------------------------------------------------------
const BACKEND_TARGET = process.env.BACKEND_TARGET || 'http://127.0.0.1:5001';
const apiProxy = createProxyMiddleware({
  target: BACKEND_TARGET,
  changeOrigin: true,
  ws: false,
  logLevel: 'warn',
});

app.use((req, res, next) => {
  if (req.path.startsWith('/api') && !req.path.startsWith('/api/ask-codex')) {
    return apiProxy(req, res, next);
  }
  return next();
});

// ----------------------------------------------------------------------------
// Optional loader demo (kept from earlier structure)
// ----------------------------------------------------------------------------
app.use('/loader', express.static(__dirname));
app.get('/loader', (_req, res) => res.sendFile(path.join(__dirname, 'index.html')));

// ----------------------------------------------------------------------------
// Frontend routing
// In dev: proxy non-API to Vite (5173)
// In prod: serve built assets with SPA fallback
// ----------------------------------------------------------------------------
const VITE_TARGET = process.env.VITE_TARGET || 'http://127.0.0.1:5173';
const DEV_MODE = process.env.VITE_DEV === '1' || process.env.NODE_ENV === 'development';

if (DEV_MODE) {
  logger.info(`Proxying frontend to ${VITE_TARGET} (DEV_MODE)`);
  app.use(
    createProxyMiddleware({
      filter: (pathname) => !pathname.startsWith('/api') && !pathname.startsWith('/api/health') && !pathname.startsWith('/loader'),
      target: VITE_TARGET,
      changeOrigin: true,
      ws: true,
      logLevel: 'warn',
    })
  );
} else {
  app.use(express.static(FRONTEND_DIST, { index: false }));
  app.get('*', (_req, res) => res.sendFile(path.join(FRONTEND_DIST, 'index.html')));
}

// ----------------------------------------------------------------------------
// Ports & server start
// ----------------------------------------------------------------------------
const STANDARD_PORTS = { BACKEND: 5001, FRONTEND: 5173, FALLBACK: 3001 };
const port = cfg.port || STANDARD_PORTS.BACKEND;

const server = app.listen(port, cfg.host, () => {
  logger.info(`Server listening on http://${cfg.host}:${port}`);
});

process.on('SIGTERM', () => {
  logger.info('SIGTERM received; shutting down');
  server.close(() => process.exit(0));
});