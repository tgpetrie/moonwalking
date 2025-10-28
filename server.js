// server.js
// BHABIT realtime bridge: poll Flask -> broadcast via socket.io

// server.js
// Bridge: poll Flask backend and broadcast via socket.io (locked ports)

import express from "express";
import http from "http";
import fetch from "node-fetch";
import { Server as SocketIOServer } from "socket.io";

const BACKEND_BASE = process.env.API_BASE_URL || "http://127.0.0.1:5001";
const PORT = Number(process.env.PORT || 5100);
const HOST = process.env.HOST || "127.0.0.1";

// --- express + http + socket.io
const app = express();
const server = http.createServer(app);

const io = new SocketIOServer(server, {
  cors: { origin: "*" },
});

app.get("/health", (req, res) => {
  res.json({ ok: true, bridge: true, ts: Date.now() });
});

// safe fetch wrapper
async function safeJson(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.warn("[bridge] non-200 from", url, res.status);
      return null;
    }
    return await res.json();
  } catch (err) {
    console.warn("[bridge] fetch fail", url, err.message);
    return null;
  }
}

async function snapshotAll() {
  const [gainers1m, gainers3m, losers3m, movers] = await Promise.all([
    safeJson(`${BACKEND_BASE}/api/component/gainers-table-1min`),
    safeJson(`${BACKEND_BASE}/api/component/gainers-table`),
    safeJson(`${BACKEND_BASE}/api/component/losers-table`),
    safeJson(`${BACKEND_BASE}/api/component/top-movers-bar`),
  ]);

  return {
    gainers1m,
    gainers3m,
    losers3m,
    banner1h: movers,
    vol1h: movers,
  };
}

async function broadcast(ioInstance) {
  const snap = await snapshotAll();
  const ts = Date.now();

  if (snap.gainers1m) ioInstance.emit("gainers1m", snap.gainers1m);
  if (snap.gainers3m) ioInstance.emit("gainers3m", snap.gainers3m);
  if (snap.losers3m) ioInstance.emit("losers3m", snap.losers3m);
  if (snap.banner1h) ioInstance.emit("banner1h", snap.banner1h);
  if (snap.vol1h) ioInstance.emit("vol1h", snap.vol1h);

  // heartbeat
  ioInstance.emit("heartbeat", { ts });

  // loop again
  setTimeout(() => broadcast(ioInstance), 5000);
}

io.on("connection", (socket) => {
  console.log("[bridge] client connected", socket.id);
});

// kick off and listen
broadcast(io);

server.listen(PORT, HOST, () => {
  console.log(`[bridge] listening on http://${HOST}:${PORT}`);
});
