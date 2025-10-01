// Pure HTTP Worker - REST endpoints only (no WebSocket/SSE)
// Works on Cloudflare free tier
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Simple health
    if (url.pathname === "/__health") {
      return json({ ok: true, mode: "http-only" });
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

  // Scheduled handler for cron triggers
  async scheduled(event, env, ctx) {
    const id = env.HUB.idFromName("global");
    const stub = env.HUB.get(id);
    // Trigger alarm manually via cron
    await stub.alarm();
  }
};

export class Hub {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.snapshots = {
      t1m: [],
      t3m: [],
      topBanner: [],
      bottomBanner: [],
      alerts: [],
      updatedAt: 0,
    };
    this.history = {};
    this.pollingInterval = 30000; // 30 seconds
    this.isPolling = false;

    state.blockConcurrencyWhile(async () => {
      const [stored, hist, kvSnap] = await Promise.all([
        state.storage.get("snapshots"),
        state.storage.get("history"),
        // Load from KV as fallback
        env.WATCHLIST_KV ? env.WATCHLIST_KV.get("latest_snapshots", "json").catch(() => null) : null
      ]);

      if (stored) {
        this.snapshots = stored;
      } else if (kvSnap) {
        // Cold start: recover from KV
        this.snapshots = kvSnap;
      }

      if (hist) this.history = hist;

      // Start polling on initialization
      this.startPolling();
    });
  }

  // Start Coinbase REST polling
  async startPolling() {
    if (this.isPolling) return;
    this.isPolling = true;

    // Set alarm for continuous polling
    const currentAlarm = await this.state.storage.getAlarm();
    if (currentAlarm == null) {
      await this.state.storage.setAlarm(Date.now() + this.pollingInterval);
    }
  }

  // Alarm handler - called automatically by Cloudflare
  async alarm() {
    await this.fetchCoinbaseData();
    // Schedule next alarm
    await this.state.storage.setAlarm(Date.now() + this.pollingInterval);
  }

  // Fetch data from Coinbase API
  async fetchCoinbaseData() {
    try {
      const productsUrl = "https://api.exchange.coinbase.com/products";
      const response = await fetch(productsUrl);

      if (!response.ok) {
        console.error("Coinbase API error:", response.status);
        return;
      }

      const products = await response.json();
      const usdPairs = products.filter(p => p.quote_currency === "USD" && p.trading_disabled === false);

      // Fetch 24h stats for top products (limit to 50 to avoid rate limits)
      const statsPromises = usdPairs.slice(0, 50).map(async (product) => {
        try {
          const statsUrl = `https://api.exchange.coinbase.com/products/${product.id}/stats`;
          const statsRes = await fetch(statsUrl);
          if (!statsRes.ok) return null;
          const stats = await statsRes.json();
          return {
            symbol: product.base_currency,
            product_id: product.id,
            current_price: parseFloat(stats.last) || 0,
            price_change_percentage_24h: stats.last && stats.open ?
              ((parseFloat(stats.last) - parseFloat(stats.open)) / parseFloat(stats.open)) * 100 : 0,
            volume_24h: parseFloat(stats.volume) || 0,
            high_24h: parseFloat(stats.high) || 0,
            low_24h: parseFloat(stats.low) || 0,
          };
        } catch (e) {
          return null;
        }
      });

      const results = (await Promise.all(statsPromises)).filter(r => r !== null);

      // Calculate 1-min and 3-min gainers from history
      this.updateSnapshots(results);

      // Cache in KV for cold-start recovery
      if (this.env.WATCHLIST_KV) {
        await this.env.WATCHLIST_KV.put("latest_snapshots", JSON.stringify(this.snapshots), {
          expirationTtl: 300 // 5 minutes
        });
      }

    } catch (error) {
      console.error("Error fetching Coinbase data:", error);
    }
  }

  // Update snapshots with new data
  updateSnapshots(results) {
    const now = Date.now();

    // Update history
    results.forEach(item => {
      if (!this.history[item.symbol]) {
        this.history[item.symbol] = [];
      }
      this.history[item.symbol].push({
        price: item.current_price,
        timestamp: now
      });
      // Keep only last 5 minutes of history
      this.history[item.symbol] = this.history[item.symbol]
        .filter(h => now - h.timestamp < 300000);
    });

    // Calculate 1-min and 3-min changes
    const gainers1m = [];
    const all3m = [];

    results.forEach(item => {
      const hist = this.history[item.symbol] || [];

      // For fresh starts with no history, use 24h data as fallback
      if (hist.length < 2) {
        // Use 24h change as proxy until we have real history
        if (item.price_change_percentage_24h && item.price_change_percentage_24h > 0) {
          gainers1m.push({
            ...item,
            price_change_percentage_1min: item.price_change_percentage_24h,
            initial_price_1min: item.current_price / (1 + item.price_change_percentage_24h / 100)
          });
        }
        all3m.push({
          ...item,
          price_change_percentage_3min: item.price_change_percentage_24h || 0,
          initial_price_3min: item.current_price / (1 + (item.price_change_percentage_24h || 0) / 100)
        });
        return;
      }

      // 1-min change
      const oneMinAgo = hist.find(h => now - h.timestamp >= 60000) || hist[0];
      if (oneMinAgo) {
        const change1m = ((item.current_price - oneMinAgo.price) / oneMinAgo.price) * 100;
        if (change1m > 0) {
          gainers1m.push({
            ...item,
            price_change_percentage_1min: change1m,
            initial_price_1min: oneMinAgo.price
          });
        }
      }

      // 3-min change
      const threeMinAgo = hist.find(h => now - h.timestamp >= 180000) || hist[0];
      if (threeMinAgo) {
        const change3m = ((item.current_price - threeMinAgo.price) / threeMinAgo.price) * 100;
        all3m.push({
          ...item,
          price_change_percentage_3min: change3m,
          initial_price_3min: threeMinAgo.price
        });
      }
    });

    // Sort and rank
    gainers1m.sort((a, b) => b.price_change_percentage_1min - a.price_change_percentage_1min);
    all3m.sort((a, b) => b.price_change_percentage_3min - a.price_change_percentage_3min);
    const gainers3m = all3m.filter(item => item.price_change_percentage_3min > 0);

    gainers1m.forEach((item, idx) => item.rank = idx + 1);
    gainers3m.forEach((item, idx) => item.rank = idx + 1);

    // Update snapshots
    this.snapshots = {
      t1m: gainers1m.slice(0, 20),
      t3m: gainers3m.slice(0, 30),
      topBanner: gainers1m.slice(0, 10),
      bottomBanner: gainers3m.slice(0, 10).map(g => ({ ...g, volume: g.volume_24h })),
      alerts: gainers1m.filter(g => g.price_change_percentage_1min > 5).slice(0, 5),
      updatedAt: now,
    };

    // Persist to storage
    this.state.storage.put("snapshots", this.snapshots);
    this.state.storage.put("history", this.history);
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

  async fetch(request) {
    const url = new URL(request.url);

    // Health
    if (url.pathname.endsWith("/health")) {
      return this._json({
        status: "ok",
        updatedAt: this.snapshots.updatedAt,
        polling: this.isPolling,
        mode: "http-only"
      });
    }

    // Server info
    if (url.pathname.endsWith("/server-info")) {
      return this._json({ ok: true, service: "durable-object-hub", t: Date.now() });
    }

    // Metrics endpoint
    if (url.pathname.endsWith("/metrics")) {
      return this._json({
        ok: true,
        connected: true,
        products: Object.keys(this.history).length,
        ticks: Object.keys(this.history).length,
        msgCount: 0,
        errCount: 0,
        since: Date.now() - 300000
      });
    }

    // Read snapshots (full dump)
    if (url.pathname.endsWith("/snapshots") && request.method === "GET") {
      return this._json(this.snapshots);
    }

    // Snapshot endpoints for specific data types (consistent {rows: [...]} format)
    if (url.pathname.endsWith("/snapshots/one-hour-price")) {
      // Return top gainers for price banner (1-min data as proxy for 1-hour)
      return this._json({ ok: true, rows: this.snapshots.t1m || [], source: "coinbase-api" });
    }

    if (url.pathname.endsWith("/snapshots/one-hour-volume")) {
      // Return volume leaders (use bottom banner data)
      return this._json({ ok: true, rows: this.snapshots.bottomBanner || [], source: "coinbase-api" });
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
      // Return losers sorted ascending by 3min change
      const losers = [...(this.snapshots.t3m || [])]
        .sort((a, b) => a.price_change_percentage_3min - b.price_change_percentage_3min)
        .slice(0, 30);
      return this._json({ ok: true, rows: losers, source: "coinbase-api" });
    }
    if (url.pathname.endsWith("/component/losers-table-3min")) {
      const losers = [...(this.snapshots.t3m || [])]
        .sort((a, b) => a.price_change_percentage_3min - b.price_change_percentage_3min)
        .slice(0, 30);
      return this._json({ ok: true, rows: losers, source: "coinbase-api" });
    }
    if (url.pathname.endsWith("/component/top-banner-scroll")) {
      // Return both items (legacy) and rows (new standard) for compatibility
      const data = this.snapshots.topBanner || [];
      return this._json({ ok: true, items: data, rows: data, source: "coinbase-api" });
    }
    if (url.pathname.endsWith("/component/bottom-banner-scroll")) {
      const data = this.snapshots.bottomBanner || [];
      return this._json({ ok: true, items: data, rows: data, source: "coinbase-api" });
    }
    if (url.pathname.endsWith("/alerts/recent")) {
      const data = this.snapshots.alerts || [];
      return this._json({ ok: true, data: data, rows: data, source: "coinbase-api" });
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
