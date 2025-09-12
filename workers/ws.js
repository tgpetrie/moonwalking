// Hybrid Worker - can work standalone or as proxy
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Simple health
    if (url.pathname === "/__health") {
      return json({ ok: true, upstream: env.UPSTREAM_URL || "direct" });
    }

    // Server info endpoint
    if (url.pathname.endsWith("/server-info")) {
      return json({ ok: true, service: "worker", t: Date.now() });
    }

    // If we have an upstream, proxy most requests to it
    if (env.UPSTREAM_URL && !url.pathname.includes("/snapshots")) {
      return withCORS(await proxyToUpstream(request, env));
    }

    // Handle requests directly via Durable Object
    const id = env.HUB.idFromName("global");
    const stub = env.HUB.get(id);
    return stub.fetch(request);
  },
};

export class Hub {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.clients = new Set();
    this.snapshots = {
      t1m: [],
      t3m: [],
      topBanner: [],
      bottomBanner: [],
      alerts: [],
      updatedAt: 0,
    };
    this.history = {};
    state.blockConcurrencyWhile(async () => {
      const [stored, hist] = await Promise.all([
        state.storage.get("snapshots"),
        state.storage.get("history")
      ]);
      if (stored) this.snapshots = stored;
      if (hist) this.history = hist;
    });
  }

  _json(data, status = 200, extra = {}) {
    return new Response(JSON.stringify(data), {
      status,
      headers: {
        "content-type": "application/json",
        "cache-control": "s-maxage=10, stale-while-revalidate=30",
        "access-control-allow-origin": "*",
        ...extra,
      },
    });
  }

  _broadcast(obj) {
    const msg = JSON.stringify(obj);
    for (const ws of [...this.clients]) {
      try { ws.send(msg); } catch { this.clients.delete(ws); }
    }
  }

  async fetch(request) {
    const url = new URL(request.url);

    // WebSocket endpoint
    if (url.pathname === "/ws") {
      const pair = new WebSocketPair();
      const [client, server] = Object.values(pair);
      server.accept();
      this.clients.add(server);
      server.addEventListener("close", () => this.clients.delete(server));
      server.addEventListener("error", () => this.clients.delete(server));
      // Send a hello with current snapshot
      server.send(JSON.stringify({ type: "hello", snapshots: this.snapshots }));
      return new Response(null, { status: 101, webSocket: client });
    }

    // Health
    if (url.pathname.endsWith("/health")) {
      return this._json({ status: "ok", clients: this.clients.size, updatedAt: this.snapshots.updatedAt });
    }

    // Server info
    if (url.pathname.endsWith("/server-info")) {
      return this._json({ ok: true, service: "worker", t: Date.now() });
    }

    // Metrics endpoint
    if (url.pathname.endsWith("/metrics")) {
      return this._json({ 
        ok: true, 
        connected: true, 
        products: Object.keys(this.history),
        ticks: Object.keys(this.history).length,
        msgCount: 0,
        errCount: 0,
        since: Date.now() - 300000
      });
    }

    // Read snapshots
    if (url.pathname.endsWith("/snapshots") && request.method === "GET") {
      return this._json(this.snapshots);
    }

    // Update snapshots (used by a scheduled worker or CI job)
    if (url.pathname.endsWith("/snapshots") && request.method === "POST") {
      const body = await request.json().catch(() => ({}));
      const next = {
        t1m: body.t1m || this.snapshots.t1m,
        t3m: body.t3m || this.snapshots.t3m,
        topBanner: body.topBanner || this.snapshots.topBanner,
        bottomBanner: body.bottomBanner || this.snapshots.bottomBanner,
        alerts: body.alerts || this.snapshots.alerts,
        updatedAt: Date.now(),
      };
      this.snapshots = next;
      if (body.history && typeof body.history === 'object') {
        this.history = body.history;
        await this.state.storage.put("history", this.history);
      }
      await this.state.storage.put("snapshots", next);
      this._broadcast({ type: "snapshots", updatedAt: next.updatedAt });
      return this._json({ ok: true, updatedAt: next.updatedAt });
    }

    // UI endpoints (return arrays in a common shape to match frontend expectations)
    if (url.pathname.endsWith("/component/gainers-table")) {
      return this._json({ ok: true, rows: this.snapshots.t3m || [], source: "coinbase-api" });
    }
    if (url.pathname.endsWith("/component/gainers-table-1min")) {
      return this._json({ ok: true, rows: this.snapshots.t1m || [], source: "coinbase-api" });
    }
    if (url.pathname.endsWith("/component/gainers-table-3min")) {
      return this._json({ ok: true, rows: this.snapshots.t3m || [], source: "coinbase-api" });
    }
    if (url.pathname.endsWith("/component/losers-table")) {
      return this._json({ ok: true, rows: this.snapshots.t3m || [], source: "coinbase-api" });
    }
    if (url.pathname.endsWith("/component/losers-table-3min")) {
      return this._json({ ok: true, rows: this.snapshots.t3m || [], source: "coinbase-api" });
    }
    if (url.pathname.endsWith("/component/top-banner-scroll")) {
      return this._json({ ok: true, items: this.snapshots.topBanner || [] });
    }
    if (url.pathname.endsWith("/component/bottom-banner-scroll")) {
      return this._json({ ok: true, items: this.snapshots.bottomBanner || [] });
    }
    if (url.pathname.endsWith("/alerts/recent")) {
      return this._json({ ok: true, data: this.snapshots.alerts || [] });
    }

    return new Response("Not found", { status: 404 });
  }
}

// ===== Helpers =====
async function proxyToUpstream(request, env) {
  const inUrl = new URL(request.url);
  const outUrl = new URL(env.UPSTREAM_URL);
  outUrl.pathname = inUrl.pathname;
  outUrl.search = inUrl.search;

  // Clone method/body/headers for proxy
  const init = {
    method: request.method,
    headers: new Headers(request.headers),
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
    redirect: "manual",
  };

  // Remove CF-specific headers that upstream won't expect
  init.headers.delete("cf-connecting-ip");
  init.headers.delete("cdn-loop");
  init.headers.delete("cf-ipcountry");

  const res = await fetch(outUrl.toString(), init);
  return new Response(res.body, { status: res.status, headers: res.headers });
}

function withCORS(response) {
  const r = new Response(response.body, response);
  r.headers.set("access-control-allow-origin", "*");
  r.headers.set("access-control-allow-headers", "*");
  r.headers.set("access-control-allow-methods", "GET,POST,OPTIONS");
  return r;
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*"
    },
  });
}