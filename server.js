import express from 'express';
import 'dotenv/config';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import handler from './api/ask-codex.js';
import { loadConfig } from './config.js';
import { logger, reqIdMiddleware } from './logger.js';

const cfg = loadConfig();
const app = express();
app.use(express.json({ limit: '2mb' }));
app.use(reqIdMiddleware);

// Serve the BHABIT logo loader + tokens style guide from the repo root in dev
const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Static assets in project root (index.html, bhabit-tokens.css, bhabit-logo-*.svg, bhabit-logo-loader.js)
app.use(express.static(__dirname));
app.get('/', (_req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.post('/api/ask-codex', (req, res) => handler(req, res));
app.get('/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime(), commit: process.env.GIT_COMMIT || null });
});

const server = app.listen(cfg.port, cfg.host, () => {
  logger.info(`Server listening on http://${cfg.host}:${cfg.port}`);
});

process.on('SIGTERM', () => {
  logger.info('SIGTERM received; shutting down');
  server.close(() => process.exit(0));
});
