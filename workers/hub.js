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
          const volBase = Number(j?.volume);
          if (!Number.isFinite(price)) return null;
          const volume_24h = Number.isFinite(volBase) ? volBase * price : 0;
          return { symbol: sym, price, volume_24h };
        } catch { return null; }
      }));
      const rows = results.filter(Boolean);

      // Get previous snapshots (to extract stored history)
      const prev = await (await stub.fetch("https://do/snapshots")).json().catch(()=>({}));
      const prevHistory = prev && prev.history ? prev.history : {};
      // Merge new prices into history
      const history = { ...prevHistory };
      for (const r of rows) {
        const arr = (history[r.symbol] || []).filter(pt => (now - (pt.t||0)) <= 70 * 60 * 1000).slice(-120);
        arr.push({ t: now, p: r.price, v: r.volume_24h });
        arr.sort((a,b)=>a.t-b.t);
        while (arr.length > 180) arr.shift();
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
        const p1c = (p1 && p1.p > 0) ? ((pNow - p1.p) / p1.p) * 100 : 0;
        const p3c = (p3 && p3.p > 0) ? ((pNow - p3.p) / p3.p) * 100 : 0;
        t1mRaw.push({ symbol: r.symbol, current_price: pNow, price_change_percentage_1min: p1c });
        t3mRaw.push({ symbol: r.symbol, current_price: pNow, price_change_percentage_3min: p3c });
      }
      const sortDesc = (arr, key) => arr.slice().sort((a,b)=>Math.abs(b[key]) - Math.abs(a[key])).map((it, i)=>({ rank: i+1, ...it }));
      const t1m = sortDesc(t1mRaw, 'price_change_percentage_1min');
      const t3m = sortDesc(t3mRaw, 'price_change_percentage_3min');

      // 1h change and volume for banners
      const topBanner = rows.map(r => {
        const arr = history[r.symbol] || [];
        const p1h = lookback(arr, 3_600_000);
        const change1h = (p1h && p1h.p > 0) ? ((r.price - p1h.p) / p1h.p) * 100 : 0;
        return { symbol: r.symbol, current_price: r.price, price_change_1h: change1h };
      }).sort((a,b)=>Math.abs(b.price_change_1h) - Math.abs(a.price_change_1h)).slice(0, 20)
       .map((it, i) => ({ rank: i+1, ...it }));

      const bottomBanner = rows.map(r => {
        const arr = history[r.symbol] || [];
        const last = arr[arr.length-1];
        const vol = last && Number.isFinite(last.v) ? last.v : 0;
        return { symbol: r.symbol, current_price: r.price, volume_24h: vol, volume_change_1h_pct: 0 };
      }).sort((a,b)=> (b.volume_24h||0) - (a.volume_24h||0)).slice(0, 20)
       .map((it, i) => ({ rank: i+1, ...it }));

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
      return this._json({ ok: true, service: "worker", t: Date.now() });
    }

    // ---- Watchlist CRUD ----
    if (url.pathname === "/watchlist" && request.method === "GET") {
      return await this._getWatchlist(request);
    }
    if (url.pathname === "/watchlist" && request.method === "POST") {
      return await this._saveWatchlist(request);
    }

    // ---- Watch Codex (metadata describing symbols, groups, or strategies) ----
    if (url.pathname === "/codex" && request.method === "GET") {
      return await this._getCodex(request);
    }
    if (url.pathname === "/codex" && request.method === "POST") {
      return await this._saveCodex(request);
    }

    // Alerts: minimal stub returning last N alerts from snapshots (or empty)
    if (url.pathname.endsWith("/alerts/recent")) {
      const limit = Math.max(1, Math.min(200, Number(url.searchParams.get('limit')) || 25));
      const alerts = Array.isArray(this.snapshots.alerts) ? this.snapshots.alerts.slice(-limit) : [];
      return this._json({ alerts });
    }

    // Banner stubs used by frontend components
    if (url.pathname === "/component/top-banner-scroll") {
      const data = Array.isArray(this.snapshots.topBanner) ? this.snapshots.topBanner : [];
      return this._json({ data });
    }
    if (url.pathname === "/component/bottom-banner-scroll") {
      const data = Array.isArray(this.snapshots.bottomBanner) ? this.snapshots.bottomBanner : [];
      return this._json({ data });
    }

    // Metrics
    if (url.pathname.endsWith("/metrics")) {
      return this._json({
        status: "ok",
        uptime_seconds: this.snapshots.updatedAt ? Math.max(0, Math.floor((Date.now() - this.snapshots.updatedAt) / 1000)) : 0,
        clients: this.clients.size,
        symbols: Object.keys(this.history || {}).length,
        updatedAt: this.snapshots.updatedAt || 0
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

    // ---- Component endpoints: real data using Coinbase tickers + history ----
    if (url.pathname.startsWith('/component/')) {
      const qpSyms = (url.searchParams.get('symbols') || '').split(',').map(s=>s.trim()).filter(Boolean);
      const symbolList = qpSyms.length ? qpSyms : String(this.env.COIN_LIST || "BTC,ETH,SOL,AMP").split(',').map(s=>s.trim()).filter(Boolean);
      const now = Date.now();
      const lookback = (arr, ms) => {
        const target = now - ms;
        let best = null;
        for (const pt of arr) { if (pt.t <= target) best = pt; else break; }
        return best;
      };
      const hist = this.history || {};
      const latest = (sym) => { const arr = hist[sym] || []; return arr[arr.length-1] || null; };

      const buildTable = (minutes, dir) => {
        const ms = minutes * 60 * 1000;
        const rows = [];
        for (const sym of symbolList) {
          const arr = hist[sym] || [];
          const last = latest(sym);
          if (!last || !Number.isFinite(last.p)) continue;
          const lb = lookback(arr, ms);
          const change = (lb && lb.p > 0) ? ((last.p - lb.p) / lb.p) * 100 : 0;
          rows.push({ symbol: sym, current_price: last.p, [`price_change_percentage_${minutes}min`]: change });
        }
        const key = minutes === 1 ? 'price_change_percentage_1min' : 'price_change_percentage_3min';
        rows.sort((a,b)=> dir === 'gainers' ? (b[key]-a[key]) : (a[key]-b[key]));
        return rows.map((r,i)=> ({ rank: i+1, ...r }));
      };

      if (url.pathname.endsWith('/gainers-table-1min')) {
        return this._json({ component: 'gainers_table', data: buildTable(1, 'gainers') });
      }
      if (url.pathname.endsWith('/gainers-table-3min') || url.pathname.endsWith('/gainers-table')) {
        return this._json({ component: 'gainers_table', data: buildTable(3, 'gainers') });
      }
      if (url.pathname.endsWith('/losers-table-3min') || url.pathname.endsWith('/losers-table')) {
        return this._json({ component: 'losers_table', data: buildTable(3, 'losers') });
      }
      if (url.pathname.endsWith('/top-banner-scroll')) {
        // Build from last snapshot
        const items = (this.snapshots.topBanner || []).map(x => ({ symbol: x.symbol, current_price: x.current_price, price_change_1h: x.price_change_1h }));
        return this._json({ data: items });
      }
      if (url.pathname.endsWith('/bottom-banner-scroll')) {
        const items = (this.snapshots.bottomBanner || []).map(x => ({ symbol: x.symbol, volume_24h: x.volume_24h, current_price: x.current_price, volume_change: x.volume_change_1h_pct || 0 }));
        return this._json({ data: items });
      }

      if (url.pathname.endsWith('/top-movers-bar')) {
        // Use 3m absolute change as mover score
        const now = Date.now();
        const hist = this.history || {};
        const lookback = (arr, ms) => {
          const target = now - ms;
          let best = null; for (const pt of arr) { if (pt.t <= target) best = pt; else break; } return best;
        };
        const syms = (String(this.env.COIN_LIST || "BTC,ETH,SOL,AMP")).split(',').map(s=>s.trim()).filter(Boolean);
        const rows = [];
        for (const s of syms) {
          const arr = hist[s] || [];
          const last = arr[arr.length-1];
          if (!last || !Number.isFinite(last.p)) continue;
          const lb = lookback(arr, 180_000);
          const change = (lb && lb.p > 0) ? ((last.p - lb.p) / lb.p) * 100 : 0;
          rows.push({ symbol: s, current_price: last.p, price_change_percentage_3min: change });
        }
        rows.sort((a,b)=> Math.abs(b.price_change_percentage_3min) - Math.abs(a.price_change_percentage_3min));
        const items = rows.slice(0, 30).map((r,i)=> ({
          rank: i+1,
          symbol: r.symbol,
          volume_24h: 0,
          volume_change: r.price_change_percentage_3min,
          current_price: r.current_price,
        }));
        return this._json({ component: 'top_movers_bar', data: items, count: items.length });
      }
    }

    if (url.pathname.endsWith('/market-overview')) {
      // basic market overview derived from symbol list snapshot
      const syms = (String(this.env.COIN_LIST || "BTC,ETH,SOL,AMP")).split(',').map(s=>s.trim()).filter(Boolean);
      const hist = this.history || {};
      let adv = 0, dec = 0, flat = 0;
      for (const s of syms) {
        const arr = hist[s] || [];
        const last = arr[arr.length-1];
        if (!last || !Number.isFinite(last.p)) continue;
        const lb = arr[0];
        const change = (lb && lb.p > 0) ? ((last.p - lb.p) / lb.p) * 100 : 0;
        if (change > 0) adv++; else if (change < 0) dec++; else flat++;
      }
      const total = adv + dec + flat;
      return this._json({
        ok: true,
        breadth: { advancers: adv, decliners: dec, flat, total },
        ts: Date.now()
      });
    }

    // ---- Minimal watchlist insight stubs to avoid 404s ----
    if (url.pathname.startsWith('/watchlist/insights')) {
      if (url.pathname.endsWith('/latest') && request.method === 'POST') {
        // Accept { symbols: [] } and return { latest: {SYM: {...}} }
        const body = await request.json().catch(()=>({ symbols: [] }));
        const out = {};
        const syms = Array.isArray(body.symbols) ? body.symbols : [];
        for (const s of syms) out[s] = null;
        return this._json({ latest: out });
      }
      if (url.pathname.endsWith('/price')) {
        return this._json({ ok: true, prices: {} });
      }
      if (url.pathname.endsWith('/log')) {
        return this._json({ ok: true, log: [] });
      }
      return this._json({ ok: true, insights: [] });
    }

    if (url.pathname === '/watchlist') {
      return this._json({ ok: true });
    }

    return new Response("Not found", { status: 404 });
  }

  // ---- Watchlist helper methods ----
  async _getWatchlist(request) {
    const user = this._userKey(request);
    const raw = await this.state.storage.get(`wl:${user}`);
    const watchlist = raw ? JSON.parse(raw) : { symbols: [] };
    return this._json({ ok: true, watchlist: watchlist.symbols });
  }

  async _saveWatchlist(request) {
    const user = this._userKey(request);
    const body = await request.json().catch(() => ({}));
    const symbols = Array.isArray(body.symbols) ? body.symbols : [];
    const data = JSON.stringify({ symbols, updatedAt: Date.now() });
    await this.state.storage.put(`wl:${user}`, data);
    // Notify subscribers
    this._broadcast({ type: "watchlist:update", user, symbols });
    return this._json({ ok: true, saved: symbols.length });
  }

  // ---- Codex helper methods ----
  async _getCodex(request) {
    const user = this._userKey(request);
    const raw = await this.state.storage.get(`codex:${user}`);
    const codex = raw ? JSON.parse(raw) : { lists: {}, notes: {} };
    return this._json({ ok: true, codex });
  }

  async _saveCodex(request) {
    const user = this._userKey(request);
    const incoming = await request.json().catch(() => ({}));
    const prevRaw = await this.state.storage.get(`codex:${user}`);
    const prev = prevRaw ? JSON.parse(prevRaw) : { lists: {}, notes: {} };
    const merged = this._deepMerge(prev, incoming);
    await this.state.storage.put(`codex:${user}`, JSON.stringify(merged));
    // Notify subscribers
    this._broadcast({ type: "codex:update", user });
    return this._json({ ok: true });
  }

  // ---- Helper methods ----
  _userKey(request) {
    // Minimal identity: can come from header/cookie; fallback to local dev
    return request.headers.get("x-user") || "dev-user";
  }

  _deepMerge(a, b) {
    if (Array.isArray(a) && Array.isArray(b)) return b;
    if (a && typeof a === "object" && b && typeof b === "object") {
      const out = { ...a };
      for (const k of Object.keys(b)) out[k] = this._deepMerge(a[k], b[k]);
      return out;
    }
    return b ?? a;
  }
}
