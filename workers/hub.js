export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    // All requests are handled by a single Durable Object instance named "global"
    const id = env.HUB.idFromName("global");
    const stub = env.HUB.get(id);
    // Optional local dev utility to trigger a refresh
    if (url.pathname === "/refresh-snapshots") {
      await this._updateSnapshots(env, stub);
      return new Response(JSON.stringify({ ok: true }), { headers: { 'content-type': 'application/json' }});
    }
    return stub.fetch(request);
  },
  // Optional: keep the DO warm on a schedule (Cron Trigger)
  async scheduled(event, env, ctx) {
    const id = env.HUB.idFromName("global");
    const stub = env.HUB.get(id);
    ctx.waitUntil(this._updateSnapshots(env, stub));
  },
  async _updateSnapshots(env, stub) {
    try {
      const list = String(env.COIN_LIST || "BTC,ETH,SOL,AMP").split(',').map(s => s.trim()).filter(Boolean);
      const now = Date.now();
      const results = await Promise.all(list.map(async (sym) => {
        try {
          const res = await fetch(`https://api.exchange.coinbase.com/products/${sym}-USD/ticker`, { headers: { 'user-agent': 'mw-hub/1.0' }});
          if (!res.ok) return null;
          const j = await res.json();
          const price = Number(j?.price);
          if (!Number.isFinite(price)) return null;
          return { symbol: sym, price };
        } catch { return null; }
      }));
      const rows = results.filter(Boolean);

      // Get previous snapshots (to extract stored history)
      const prev = await (await stub.fetch("https://do/snapshots")).json().catch(()=>({}));
      const prevHistory = prev && prev.history ? prev.history : {};
      // Merge new prices into history
      const history = { ...prevHistory };
      for (const r of rows) {
        const arr = (history[r.symbol] || []).slice(-5);
        arr.push({ t: now, p: r.price });
        arr.sort((a,b)=>a.t-b.t);
        while (arr.length > 6) arr.shift();
        history[r.symbol] = arr;
      }

      const lookback = (arr, ms) => {
        const target = now - ms;
        let best = null;
        for (const pt of arr) { if (pt.t <= target) best = pt; else break; }
        return best;
      };

      const t1mRaw = [], t3mRaw = [];
      for (const r of rows) {
        const arr = history[r.symbol] || [];
        const pNow = r.price;
        const p1 = lookback(arr, 60_000);
        const p3 = lookback(arr, 180_000);
        const c1 = (p1 && p1.p > 0) ? ((pNow - p1.p) / p1.p) * 100 : 0;
        const c3 = (p3 && p3.p > 0) ? ((pNow - p3.p) / p3.p) * 100 : 0;
        t1mRaw.push({ symbol: r.symbol, current_price: pNow, price_change_percentage_1min: c1 });
        t3mRaw.push({ symbol: r.symbol, current_price: pNow, price_change_percentage_3min: c3 });
      }
      const sortDesc = (arr, key) => arr.slice().sort((a,b)=>Math.abs(b[key]) - Math.abs(a[key])).map((it, i)=>({ rank: i+1, ...it }));
      const t1m = sortDesc(t1mRaw, 'price_change_percentage_1min');
      const t3m = sortDesc(t3mRaw, 'price_change_percentage_3min');
      const topBanner = t1m.slice(0, 20).map(it => ({ rank: it.rank, symbol: it.symbol, current_price: it.current_price, price_change_1h: it.price_change_percentage_1min }));
      const bottomBanner = t3m.slice(0, 20).map(it => ({ rank: it.rank, symbol: it.symbol, current_price: it.current_price, volume_change_1h_pct: 0, volume_24h: 0 }));

      await stub.fetch("https://do/snapshots", {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ topBanner, bottomBanner, t1m, t3m, alerts: [], history })
      });
    } catch (e) {
      // swallow errors; add logging later
    }
  }
}

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
      return this._json({ status: "running", updatedAt: this.snapshots.updatedAt });
    }

    // Metrics
    if (url.pathname.endsWith("/metrics")) {
      return this._json({
        status: "ok",
        uptime_seconds: Math.floor((Date.now() - this.snapshots.updatedAt) / 1000),
        clients: this.clients.size,
        updatedAt: this.snapshots.updatedAt
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

    // ---- Component endpoints: gainers/losers, 1min/3min ----
    if (url.pathname.startsWith('/component/')) {
      const slug = url.pathname.slice('/component/'.length); // e.g., "gainers-table-1min"
      const isGainers = slug.includes('gainers');
      const isLosers  = slug.includes('losers');
      const is1m      = slug.includes('1min');
      const is3m      = slug.includes('3min') || (!is1m && !slug.includes('1min')); // default to 3m if no timeframe specified

      // symbols from ?symbols= or env.COIN_LIST
      const symbols = (() => {
        const fromQuery = (url.searchParams.get('symbols') || '')
          .split(',').map(s => s.trim()).filter(Boolean);
        const fromEnv = ((this.env?.COIN_LIST || '') + '')
          .split(',').map(s => s.trim()).filter(Boolean);
        return (fromQuery.length ? fromQuery : fromEnv).slice(0, 50);
      })();

      const randIn = (lo, hi) => Math.round((lo + Math.random() * (hi - lo)) * 1000) / 1000;
      const priceFor = (sym) =>
        sym === 'BTC' ? randIn(95000, 130000) :
        sym === 'ETH' ? randIn(3000,  5500)   :
                        randIn(0.1,   300);

      const rows = symbols.map((sym, idx) => {
        let pct = randIn(0.05, 4.0);      // always non-zero 0.05%..4%
        if (isLosers) pct = -pct;         // losers are negative
        const base = priceFor(sym);

        const row = {
          rank: idx + 1,
          symbol: sym,
          current_price: Math.round(base * 100) / 100,
        };
        if (is1m) row.price_change_percentage_1min = pct;
        if (is3m) row.price_change_percentage_3min = pct;
        return row;
      });

      const sortKey = is1m ? 'price_change_percentage_1min'
                           : 'price_change_percentage_3min';
      rows.sort((a, b) => (isGainers ? b[sortKey] - a[sortKey]
                                     : a[sortKey] - b[sortKey]));

      return new Response(JSON.stringify({ component: slug, data: rows }), {
        status: 200,
        headers: {
          'content-type': 'application/json',
          'cache-control': 's-maxage=10, stale-while-revalidate=30'
        }
      });
    }

    return new Response("Not found", { status: 404 });
  }
}
