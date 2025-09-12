import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { createServer } from 'http';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();

// Serve static files from frontend/dist
app.use(express.static(path.join(__dirname, 'frontend/dist')));

// Proxy API requests to the worker
app.use('/api', createProxyMiddleware({
  target: 'http://127.0.0.1:8787',
  changeOrigin: true,
  pathRewrite: {
    '^/api': '', // Remove /api prefix when forwarding to worker
  },
  onError: (err, req, res) => {
    console.error('Proxy error:', err.message);
    res.status(500).json({ error: 'Proxy error' });
  },
  onProxyReq: (proxyReq, req, res) => {
    console.log(`Proxying: ${req.method} ${req.url} -> http://127.0.0.1:8787${req.url.replace('/api', '')}`);
  }
}));

// Proxy WebSocket connections to the worker
const wsProxy = createProxyMiddleware({
  target: 'ws://127.0.0.1:8787',
  changeOrigin: true,
  ws: true, // Enable WebSocket proxying
  xfwd: true,
  logLevel: 'warn',
  onError: (err, req, res) => {
    console.error('WebSocket proxy error:', err.message);
    if (res && res.writeHead) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('WebSocket proxy error');
    }
  }
});

// Attach explicit /ws route
app.use('/ws', wsProxy);

// Fallback to index.html for SPA routing
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'frontend/dist/index.html'));
});

const PORT = 8789;
const server = createServer(app);

// Ensure upgrade events reach the WS proxy
server.on('upgrade', (req, socket, head) => {
  if (req.url && req.url.startsWith('/ws')) {
    wsProxy.upgrade(req, socket, head);
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Proxy server running on http://127.0.0.1:${PORT}`);
  console.log('Frontend: Serving static files from frontend/dist');
  console.log('API: Proxying /api/* to http://127.0.0.1:8787');
  console.log('WebSocket: Proxying /ws to http://127.0.0.1:8787/ws');
});