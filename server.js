import express from 'express';
import handler from './api/ask-codex.js';
import { loadConfig } from './config.js';
import { logger, reqIdMiddleware } from './logger.js';

const cfg = loadConfig();
const app = express();
app.use(express.json({ limit: '2mb' }));
app.use(reqIdMiddleware);

app.post('/api/ask-codex', (req, res) => handler(req, res));
app.get('/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime(), commit: process.env.GIT_COMMIT || null });
});

const server = app.listen(cfg.port, () => {
  logger.info(`Server listening on http://localhost:${cfg.port}`);
});

process.on('SIGTERM', () => {
  logger.info('SIGTERM received; shutting down');
  server.close(() => process.exit(0));
});
