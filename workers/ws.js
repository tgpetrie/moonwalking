// workers/ws.js

// ---------- Worker entry: forwards requests to the Durable Object ----------
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Lightweight direct health for quick pings (doesn't involve DO)
    if (url.pathname === "/server-info") {
      return json({ ok: true, service: "worker", t: Date.now() });
    }

    // Everything else -> Hub DO
    const id = env.HUB.idFromName("global-usd");
    const stub = env.HUB.get(id);
    return stub.fetch(request);
  },
};

function json(obj, init = {}) {
  const headers = new Headers(init.headers || {});
  if (!headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  return new Response(JSON.stringify(obj), { ...init, headers });
}

// ---------- Durable Object that manages Coinbase WS + in-memory state ----------
export class Hub {
  constructor(state, env) {
    this.state = state;
    this.env = env;

    this.started = false;
    this.startedAt = 0;
    this.connected = false;

    this.ws = null;
    this.heartbeatTimer = null;

    // Markets and ticks (live)
    this.products = [];                      // ["BTC-USD", ...]
    this.ticks = new Map();                  // product_id -> { price, t }
    this.firstPrice = new Map();             // product_id -> first seen price (for %Δ since first tick)

    // simple counters
    this.msgCount = 0;
    this.errCount = 0;
  }

  async fetch(request) {
    const url = new URL(request.url);

    // Universal CORS for dev convenience (adjust if you want to lock this down)
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(),
      });
    }

    // Healthz (no lazy start: shows current)
    if (url.pathname === "/healthz") {
      return json({
        ok: true,
        connected: this.connected,
        products: this.products.length,
        ticks: this.ticks.size,
        uptime_s: this.startedAt ? Math.floor((Date.now() - this.startedAt) / 1000) : 0,
      }, { headers: corsHeaders() });
    }

    // Lazily start the WS for data routes
    const needsData =
      url.pathname.startsWith("/component/") ||
      url.pathname === "/metrics";

    if (needsData) {
      await this.ensureStarted();
    }

    if (url.pathname === "/metrics") {
      return json({
        ok: true,
        connected: this.connected,
        products: this.products,
        ticks: this.ticks.size,
        msgCount: this.msgCount,
        errCount: this.errCount,
        since: this.startedAt,
      }, { headers: corsHeaders() });
    }

    if (
      url.pathname === "/component/gainers-table" ||
      url.pathname === "/component/gainers-table-1min"
    ) {
      const limit = num(url.searchParams.get("limit"), 25);
      const rows = this.snapshotRows(limit, "desc");
      return json({ ok: true, rows, source: "coinbase-pro-ws" }, { headers: corsHeaders() });
    }

    if (
      url.pathname === "/component/losers-table" ||
      url.pathname === "/component/losers-table-3min"
    ) {
      const limit = num(url.searchParams.get("limit"), 25);
      const rows = this.snapshotRows(limit, "asc");
      return json({ ok: true, rows, source: "coinbase-pro-ws" }, { headers: corsHeaders() });
    }

    if (url.pathname === "/server-info") {
      return json({ ok: true, service: "durable-object", t: Date.now() }, { headers: corsHeaders() });
    }

    return new Response("Not found", { status: 404, headers: corsHeaders() });
  }

  // Build a current "table" just from live ticks.
  // Sort by pct change since first seen price; tie-breaker by most recent timestamp.
  snapshotRows(limit, direction /* "asc" losers, "desc" gainers */) {
    const rows = [];
    for (const [product_id, v] of this.ticks) {
      const first = this.firstPrice.get(product_id);
      const price = Number(v.price);
      const pct = (first && first > 0) ? ((price - first) / first) * 100 : 0;
      rows.push({
        symbol: product_id,
        price,
        pct,          // %Δ since first seen
        t: v.t,
      });
    }

    rows.sort((a, b) => {
      if (direction === "asc") {
        if (a.pct !== b.pct) return a.pct - b.pct;
      } else {
        if (a.pct !== b.pct) return b.pct - a.pct;
      }
      // tie-break by recency
      return b.t - a.t;
    });

    return rows.slice(0, limit);
  }

  async ensureStarted() {
    if (this.started) return;

    this.started = true;
    this.startedAt = Date.now();

    // Resolve product list
    const quote = (this.env.QUOTE || "USD").toUpperCase();
    const coinList = (this.env.COIN_LIST || "").trim();

    if (coinList) {
      // explicit allow-list from env
      this.products = coinList
        .split(",")
        .map(s => s.trim().toUpperCase())
        .filter(Boolean)
        .map(base => `${base}-${quote}`);
    } else {
      // discover all USD pairs that are online
      this.products = await this.fetchUsdPairs(quote);
    }

    await this.connectCoinbase();
  }

  async fetchUsdPairs(quote = "USD") {
    try {
      const r = await fetch("https://api.exchange.coinbase.com/products", {
        headers: { "user-agent": "mw-hub-do/1.0" },
      });
      if (!r.ok) throw new Error(`products ${r.status}`);
      const data = await r.json();
      return data
        .filter(p => p && p.quote_currency === quote && p.status === "online")
        .map(p => p.id)
        .slice(0, 200); // safety cap
    } catch (e) {
      this.errCount++;
      // fallback to a small core if discovery fails
      return ["BTC-USD", "ETH-USD", "SOL-USD", "AMP-USD"];
    }
  }

  async connectCoinbase() {
    const url = "wss://ws-feed.exchange.coinbase.com"; // public, no auth
    try {
      const ws = new WebSocket(url);
      this.ws = ws;

      ws.addEventListener("open", () => {
        const sub = {
          type: "subscribe",
          product_ids: this.products,
          channels: ["ticker"],
        };
        ws.send(JSON.stringify(sub));
        this.connected = true;

        // heartbeat ping (helps keep connections alive)
        this.heartbeatTimer = setInterval(() => {
          try { ws.send(JSON.stringify({ type: "ping" })); } catch {}
        }, 15000);
      });

      ws.addEventListener("message", (evt) => {
        try {
          this.msgCount++;
          const m = JSON.parse(evt.data);
          if (m.type === "ticker" && m.product_id && m.price) {
            const price = Number(m.price);
            const t = m.time ? new Date(m.time).getTime() : Date.now();

            // first seen price
            if (!this.firstPrice.has(m.product_id)) {
              this.firstPrice.set(m.product_id, price);
            }
            this.ticks.set(m.product_id, { price, t });
          }
        } catch (e) {
          this.errCount++;
        }
      });

      ws.addEventListener("close", () => {
        this.connected = false;
        if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null; }
        // try a gentle backoff reconnect in background
        this.state.waitUntil(this.backoffReconnect());
      });

      ws.addEventListener("error", () => {
        this.errCount++;
        this.connected = false;
        if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null; }
        this.state.waitUntil(this.backoffReconnect());
      });
    } catch (e) {
      this.errCount++;
      this.connected = false;
      this.state.waitUntil(this.backoffReconnect());
    }
  }

  async backoffReconnect() {
    // simple backoff
    await sleep(2000 + Math.floor(Math.random() * 2000));
    if (!this.connected) {
      await this.connectCoinbase();
    }
  }
}

function sleep(ms) { return new Promise(res => setTimeout(res, ms)); }

function corsHeaders() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type,authorization",
    "content-type": "application/json",
  };
}

function num(v, fallback) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}
