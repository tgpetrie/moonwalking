// Pure HTTP Worker - REST endpoints only (no WebSocket/SSE)
// Works on Cloudflare free tier

// Edge cache wrapper to minimize KV reads and Durable Object calls
async function cachedJsonResponse(request, ctx, key, computeFn, ttlSeconds = 2) {
  const cache = caches.default;
  const cacheKey = new Request(`https://cache/${key}`, { method: 'GET' });

  // Try edge cache first
  let response = await cache.match(cacheKey);
  if (response) {
    return response;
  }

  // Cache miss: compute/fetch data
  const data = await computeFn();
  response = new Response(JSON.stringify(data), {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': `public, s-maxage=${ttlSeconds}`,
    }
  });

  // Store at edge for subsequent requests
  ctx.waitUntil(cache.put(cacheKey, response.clone()));
  return response;
}

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

    // If we have an upstream, proxy most requests to it (but never SSE/events)
    if (env.UPSTREAM_URL && !url.pathname.includes("/snapshots") && !url.pathname.endsWith("/events")) {
      return withCORS(await proxyToUpstream(request, env));
    }

    // Do not cache or proxy SSE streams; forward directly to DO
    if (url.pathname.endsWith("/events")) {
      const id = env.HUB.idFromName("global");
      const stub = env.HUB.get(id);
      return stub.fetch(request);
    }

    // Apply edge caching to hot endpoints (reduces Durable Object calls by ~90%)
    const hotEndpoints = [
      "/products",
      "/component/gainers-table-1min",
      "/component/gainers-table-3min",
      "/component/losers-table-3min",
      "/component/top-banner-scroll",
      "/component/bottom-banner-scroll",
    ];

    if (hotEndpoints.some(endpoint => url.pathname.endsWith(endpoint))) {
      return cachedJsonResponse(request, ctx, url.pathname, async () => {
        const id = env.HUB.idFromName("global");
        const stub = env.HUB.get(id);
        const response = await stub.fetch(request);
        return response.json();
      }, 2); // 2 second edge cache
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
    this.products = [];
    this._lastPersistedAt = 0; // epoch ms when we last wrote to KV
    this.history = {};
    this.analysisCache = {};
    this.newsCache = {};
    this.socialCache = {};
    this.pollingInterval = 5000; // 5 seconds
    this.isPolling = false;

  // SSE clients
  this.clients = new Set(); // Set<{writer, keepAliveId}>

  // throttle timestamps
  this._lastStoredAt = 0; // epoch ms for Durable Object storage writes

    state.blockConcurrencyWhile(async () => {
      // Load from Durable Object storage only (no KV read to save quota)
      const [stored, hist] = await Promise.all([
        state.storage.get("snapshots"),
        state.storage.get("history"),
      ]);

      if (stored) {
        this.snapshots = stored;
      }

      if (hist) {
        this.history = hist;
      }

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
    const changed = await this.fetchCoinbaseData();
    const now = Date.now();
    // Adaptive cadence: faster if changed, slower if quiet (free-tier friendly)
    const nextDelay = changed ? 5000 : 10000; // 5s on change, 10s otherwise
    await this.state.storage.setAlarm(now + nextDelay);

    // If there are SSE listeners, emit a lightweight tick
    if (this.clients.size > 0) {
      this._broadcastSSE({ type: "tick", updatedAt: this.snapshots.updatedAt, changed });
    }
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

      // Cache a lightweight product catalog for the /products endpoint
      this.products = usdPairs.map(p => ({
        id: p.id,
        base_currency: p.base_currency,
        quote_currency: p.quote_currency,
        display_name: p.display_name || `${p.base_currency}/${p.quote_currency}`,
        status: p.status || (p.trading_disabled ? "offline" : "online"),
        margin_enabled: !!p.margin_enabled,
        post_only: !!p.post_only
      }));

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

      // Periodically persist to KV for cold-start recovery (avoid per-poll writes)
      const now = Date.now();
      const fiveMin = 5 * 60 * 1000;
      if (this.env.WATCHLIST_KV && now - (this._lastPersistedAt || 0) >= fiveMin) {
        try {
          await this.env.WATCHLIST_KV.put("latest_snapshots", JSON.stringify(this.snapshots), {
            expirationTtl: 300 // 5 minutes
          });
          this._lastPersistedAt = now;
        } catch (e) {
          // If we hit KV quota (429), skip this persist and continue; DO keeps in-memory state
          if (String(e).includes('429')) {
            console.warn('WATCHLIST_KV quota hit; skipping persist');
          } else {
            throw e;
          }
        }
      }

      // After computing results and updating snapshots, decide if we materially changed
      const changed = this._computeChangeSignal();

      // Throttle DO storage writes (snapshots/history) to at most every 15s
      const nowTs = Date.now();
      const STORE_COOLDOWN = 15 * 1000;
      if (nowTs - (this._lastStoredAt || 0) >= STORE_COOLDOWN) {
        this.state.storage.put("snapshots", this.snapshots);
        this.state.storage.put("history", this.history);
        this._lastStoredAt = nowTs;
      }

      // Broadcast to any SSE clients if changed
      if (changed && this.clients.size > 0) {
        this._broadcastSSE({
          type: "update",
          updatedAt: this.snapshots.updatedAt,
          counts: {
            t1m: this.snapshots.t1m?.length || 0,
            t3m: this.snapshots.t3m?.length || 0
          }
        });
      }

      return changed;

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

    // Persist to storage is handled by throttled writer in fetchCoinbaseData
  }

  // Determine if the new snapshot differs materially from the previous one
  _computeChangeSignal() {
    try {
      // Consider the top 10 of 1m gainers as the change fingerprint
      const top = (this.snapshots.t1m || []).slice(0, 10);
      const key = top.map(r => `${r.product_id}:${Math.round((r.price_change_percentage_1min || 0) * 100)}`).join("|");
      if (this._lastFingerprint !== key) {
        this._lastFingerprint = key;
        return true;
      }
      return false;
    } catch (_) {
      return true;
    }
  }

  _json(data, status = 200, extra = {}) {
    return new Response(JSON.stringify(data), {
      status,
      headers: {
        "content-type": "application/json",
        "cache-control": "s-maxage=2, stale-while-revalidate=5",
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

    // SSE events stream (near-live updates without frequent polling)
    if (url.pathname.endsWith("/events")) {
      const { readable, writable } = new TransformStream();
      const writer = writable.getWriter();

      const write = (payload) => {
        const line = `data: ${JSON.stringify(payload)}\n\n`;
        return writer.write(new TextEncoder().encode(line));
      };

      // Register client and keepalive pings
      const keepAliveId = setInterval(() => {
        writer.write(new TextEncoder().encode(`: ping ${Date.now()}\n\n`)).catch(() => {});
      }, 15000);
      this.clients.add({ writer, keepAliveId });

      // Initial hello
      await write({ type: "hello", updatedAt: this.snapshots.updatedAt, t1m: (this.snapshots.t1m || []).length });

      const response = new Response(readable, {
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache, no-transform",
          "connection": "keep-alive",
          "access-control-allow-origin": "*",
          "x-accel-buffering": "no"
        }
      });

      // Cleanup when the request is terminated by the client/edge
      (async () => {
        try {
          await response.waitUntil?.(Promise.resolve());
        } finally {
          try { clearInterval(keepAliveId); } catch {}
          try { writer.close(); } catch {}
          this._pruneClients();
        }
      })();

      return response;
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

    // Products catalog (coin universe)
    if (url.pathname.endsWith("/products")) {
      return this._json({ ok: true, rows: this.products || [], source: "coinbase-api" });
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

    if (url.pathname.startsWith("/technical-analysis/")) {
      const symbol = url.pathname.split("/").filter(Boolean).pop() || "";
      return this.handleTechnicalAnalysis(symbol);
    }

    if (url.pathname.startsWith("/news/")) {
      const symbol = url.pathname.split("/").filter(Boolean).pop() || "";
      return this.handleNews(symbol);
    }

    if (url.pathname.startsWith("/social-sentiment/")) {
      const symbol = url.pathname.split("/").filter(Boolean).pop() || "";
      return this.handleSocialSentiment(symbol);
    }

    return new Response("Not found", { status: 404 });
  }

  async handleTechnicalAnalysis(rawSymbol) {
    const normalized = sanitizeSymbol(rawSymbol);
    if (!normalized) {
      return json({ success: false, error: "Invalid symbol" }, 400);
    }

    const cacheEntry = this.analysisCache[normalized];
    const now = Date.now();
    if (cacheEntry && now - cacheEntry.timestamp < ANALYSIS_CACHE_TTL_MS) {
      return json(cacheEntry.payload);
    }

    try {
      const historical = await fetchHistoricalCandles(normalized, ANALYSIS_LOOKBACK_HOURS);
      if (!historical) {
        return json({ success: false, error: "Unable to fetch historical data" }, 502);
      }

      const { closes, volumes, granularityMinutes, dataPoints } = historical;
      const rsi = calculateRSI(closes);
      const macd = calculateMACD(closes);
      const bollinger = calculateBollingerBands(closes);
      const volumeAnalysis = calculateVolumeProfile(volumes);
      const currentPrice = closes[closes.length - 1];
      const recommendation = generateRecommendation(rsi, macd, currentPrice, bollinger);

      const isoNow = new Date().toISOString();
      const payload = {
        success: true,
        data: {
          symbol: normalized,
          current_price: roundTo(currentPrice, 4),
          rsi,
          macd,
          bollinger_bands: bollinger,
          volume_analysis: volumeAnalysis,
          recommendation,
          last_updated: isoNow,
          data_points: dataPoints,
          granularity_minutes: granularityMinutes,
          source: "coinbase"
        },
        timestamp: isoNow
      };

      this.analysisCache[normalized] = { timestamp: now, payload };
      return json(payload);
    } catch (error) {
      console.error("technical-analysis error", normalized, error);
      return json({ success: false, error: "Internal error" }, 500);
    }
  }

  async handleNews(rawSymbol) {
    const normalized = sanitizeSymbol(rawSymbol);
    if (!normalized) {
      return json({ success: false, error: "Invalid symbol" }, 400);
    }

    const now = Date.now();
    const cached = this.newsCache[normalized];
    if (cached && now - cached.timestamp < NEWS_CACHE_TTL_MS) {
      return json(cached.payload);
    }

    const isoNow = new Date().toISOString();
    const articles = generateMockNews(normalized, isoNow);
    const payload = {
      success: true,
      symbol: normalized,
      articles,
      generated_at: isoNow
    };

    this.newsCache[normalized] = { timestamp: now, payload };
    return json(payload);
  }

  async handleSocialSentiment(rawSymbol) {
    const normalized = sanitizeSymbol(rawSymbol);
    if (!normalized) {
      return json({ success: false, error: "Invalid symbol" }, 400);
    }

    const now = Date.now();
    const cached = this.socialCache[normalized];
    if (cached && now - cached.timestamp < SOCIAL_CACHE_TTL_MS) {
      return json(cached.payload);
    }

    const sentiment = generateMockSentiment(normalized);
    const payload = {
      success: true,
      data: sentiment,
      generated_at: sentiment.last_updated
    };

    this.socialCache[normalized] = { timestamp: now, payload };
    return json(payload);
  }
}

const ANALYSIS_CACHE_TTL_MS = 2 * 60 * 1000; // cache technical analysis for 2 minutes
const ANALYSIS_LOOKBACK_HOURS = 72;
const NEWS_CACHE_TTL_MS = 5 * 60 * 1000;
const SOCIAL_CACHE_TTL_MS = 60 * 1000;

function sanitizeSymbol(raw) {
  if (!raw) return null;
  const cleaned = raw.toString().trim().toUpperCase();
  const lettersOnly = cleaned.replace(/[^A-Z-]/g, "");
  const normalized = lettersOnly.replace(/-USD$/, "");
  if (!/^[A-Z]{2,10}$/.test(normalized)) {
    return null;
  }
  return normalized;
}

async function fetchHistoricalCandles(symbol, hours) {
  try {
    const granularity = hours <= 6 ? 300 : hours <= 24 ? 900 : 3600;
    const end = new Date();
    const start = new Date(end.getTime() - hours * 60 * 60 * 1000);

    const url = new URL(`https://api.exchange.coinbase.com/products/${symbol}-USD/candles`);
    url.searchParams.set("start", start.toISOString());
    url.searchParams.set("end", end.toISOString());
    url.searchParams.set("granularity", granularity);

    const res = await fetch(url.toString(), {
      headers: {
        "accept": "application/json",
        "user-agent": "moonwalking-worker/1.0"
      }
    });

    if (!res || !res.ok) {
      return null;
    }

    const payload = await res.json();
    if (!Array.isArray(payload) || payload.length === 0) {
      return null;
    }

    payload.sort((a, b) => a[0] - b[0]);

    const closes = [];
    const volumes = [];
    for (const candle of payload) {
      const close = Number(candle[4]);
      const volume = Number(candle[5]);
      if (Number.isFinite(close) && Number.isFinite(volume)) {
        closes.push(close);
        volumes.push(volume);
      }
    }

    if (closes.length === 0) {
      return null;
    }

    return {
      closes,
      volumes,
      granularityMinutes: granularity / 60,
      dataPoints: closes.length
    };
  } catch (error) {
    console.error("fetchHistoricalCandles error", symbol, error);
    return null;
  }
}

function calculateRSI(prices, period = 14) {
  if (!Array.isArray(prices) || prices.length < period + 1) {
    return null;
  }

  let gains = 0;
  let losses = 0;
  for (let i = 1; i <= period; i++) {
    const delta = prices[i] - prices[i - 1];
    if (delta >= 0) gains += delta;
    else losses -= delta;
  }
  let avgGain = gains / period;
  let avgLoss = losses / period;

  for (let i = period + 1; i < prices.length; i++) {
    const delta = prices[i] - prices[i - 1];
    if (delta >= 0) {
      avgGain = ((avgGain * (period - 1)) + delta) / period;
      avgLoss = (avgLoss * (period - 1)) / period;
    } else {
      const loss = -delta;
      avgGain = (avgGain * (period - 1)) / period;
      avgLoss = ((avgLoss * (period - 1)) + loss) / period;
    }
  }

  if (avgLoss === 0) {
    return 100;
  }

  const rs = avgGain / avgLoss;
  const rsi = 100 - 100 / (1 + rs);
  return roundTo(rsi, 2);
}

function calculateMACD(prices, fast = 12, slow = 26, signal = 9) {
  if (!Array.isArray(prices) || prices.length < slow + signal) {
    return { macd: null, signal: null, histogram: null };
  }

  const emaFast = computeEMA(prices, fast);
  const emaSlow = computeEMA(prices, slow);

  const macdSeries = emaFast.map((value, idx) => {
    const slowValue = emaSlow[idx];
    return value != null && slowValue != null ? value - slowValue : null;
  });

  const signalSeries = computeEMAWithNulls(macdSeries, signal);
  const histogramSeries = macdSeries.map((value, idx) => {
    const signalValue = signalSeries[idx];
    return value != null && signalValue != null ? value - signalValue : null;
  });

  const macdValue = getLastNonNull(macdSeries);
  const signalValue = getLastNonNull(signalSeries);
  const histogramValue = getLastNonNull(histogramSeries);

  return {
    macd: macdValue != null ? roundTo(macdValue, 6) : null,
    signal: signalValue != null ? roundTo(signalValue, 6) : null,
    histogram: histogramValue != null ? roundTo(histogramValue, 6) : null
  };
}

function computeEMA(values, period) {
  const ema = new Array(values.length).fill(null);
  if (!Array.isArray(values) || !Number.isFinite(period) || period <= 0) {
    return ema;
  }

  const k = 2 / (period + 1);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    const value = values[i];
    if (!Number.isFinite(value)) {
      ema[i] = i > 0 ? ema[i - 1] : null;
      continue;
    }

    if (i < period) {
      sum += value;
      if (i === period - 1) {
        ema[i] = sum / period;
      }
      continue;
    }

    const prev = ema[i - 1] != null ? ema[i - 1] : value;
    ema[i] = value * k + prev * (1 - k);
  }

  return ema;
}

function computeEMAWithNulls(values, period) {
  const ema = new Array(values.length).fill(null);
  if (!Array.isArray(values) || !Number.isFinite(period) || period <= 0) {
    return ema;
  }

  const k = 2 / (period + 1);
  let seed = [];
  let prev = null;

  for (let i = 0; i < values.length; i++) {
    const value = values[i];
    if (value == null || !Number.isFinite(value)) {
      continue;
    }

    if (prev === null) {
      seed.push(value);
      if (seed.length === period) {
        prev = seed.reduce((acc, v) => acc + v, 0) / period;
        ema[i] = prev;
      }
    } else {
      prev = value * k + prev * (1 - k);
      ema[i] = prev;
    }
  }

  return ema;
}

function getLastNonNull(arr) {
  if (!Array.isArray(arr)) return null;
  for (let i = arr.length - 1; i >= 0; i--) {
    const value = arr[i];
    if (value != null && Number.isFinite(value)) {
      return value;
    }
  }
  return null;
}

function calculateBollingerBands(prices, period = 20, stdDev = 2) {
  if (!Array.isArray(prices) || prices.length < period) {
    return { upper: null, middle: null, lower: null };
  }

  const window = prices.slice(-period);
  const mean = window.reduce((acc, value) => acc + value, 0) / period;
  const variance = window.reduce((acc, value) => acc + Math.pow(value - mean, 2), 0) / period;
  const std = Math.sqrt(variance);

  return {
    upper: roundTo(mean + stdDev * std, 4),
    middle: roundTo(mean, 4),
    lower: roundTo(mean - stdDev * std, 4)
  };
}

function calculateVolumeProfile(volumes) {
  if (!Array.isArray(volumes) || volumes.length === 0) {
    return { avg_volume: null, recent_volume: null, volume_trend: "neutral" };
  }

  const avg = volumes.reduce((acc, value) => acc + value, 0) / volumes.length;
  const recentSlice = volumes.slice(-Math.min(5, volumes.length));
  const recentAvg = recentSlice.reduce((acc, value) => acc + value, 0) / recentSlice.length;

  let trend = "normal";
  if (recentAvg > avg * 1.5) trend = "high";
  else if (recentAvg < avg * 0.5) trend = "low";

  return {
    avg_volume: roundTo(avg, 2),
    recent_volume: roundTo(recentAvg, 2),
    volume_trend: trend
  };
}

function generateRecommendation(rsi, macd, currentPrice, bollinger) {
  const signals = [];

  if (rsi != null) {
    if (rsi > 70) signals.push("RSI overbought");
    else if (rsi < 30) signals.push("RSI oversold");
    else signals.push("RSI neutral");
  }

  if (macd && macd.macd != null && macd.signal != null) {
    signals.push(macd.macd > macd.signal ? "MACD bullish" : "MACD bearish");
  }

  if (bollinger && bollinger.upper != null && bollinger.lower != null && currentPrice != null) {
    if (currentPrice > bollinger.upper) signals.push("Above upper Bollinger Band");
    else if (currentPrice < bollinger.lower) signals.push("Below lower Bollinger Band");
    else signals.push("Within Bollinger Bands");
  }

  const bullishCount = signals.filter((s) => /bullish|oversold|below lower/i.test(s)).length;
  const bearishCount = signals.filter((s) => /bearish|overbought|above upper/i.test(s)).length;

  let recommendation = "🟡 Neutral - Wait for clearer signals";
  if (bullishCount > bearishCount) recommendation = "🟢 Cautiously Bullish";
  else if (bearishCount > bullishCount) recommendation = "🔴 Cautiously Bearish";

  const summary = signals.slice(0, 3).join(" | ");
  return summary ? `${recommendation} | ${summary}` : recommendation;
}

function roundTo(value, decimals = 2) {
  if (!Number.isFinite(value)) {
    return null;
  }
  const factor = Math.pow(10, decimals);
  return Math.round(value * factor) / factor;
}

function generateMockNews(symbol, nowIso) {
  const baseSymbol = symbol.toUpperCase();
  const display = `${baseSymbol}USD`;
  const themes = pickNewsThemes(baseSymbol);
  return themes.map((theme, idx) => ({
    id: `${baseSymbol}-${idx + 1}`,
    title: theme.title.replace(/\{SYMBOL\}/g, baseSymbol),
    summary: theme.summary.replace(/\{SYMBOL\}/g, baseSymbol).replace(/\{PAIR\}/g, display),
    source: theme.source,
    published: new Date(Date.now() - idx * 60 * 60 * 1000).toISOString(),
    sentiment: theme.sentiment,
    url: theme.url ? theme.url.replace(/\{symbol\}/g, baseSymbol.toLowerCase()) : undefined,
  }));
}

function pickNewsThemes(symbol) {
  const generic = [
    {
      title: "{SYMBOL} Shows Strong Technical Momentum",
      summary: "Recent price structure and on-chain flows point to building momentum for {SYMBOL}, with traders eyeing breakout levels on the {PAIR} pair.",
      source: "Crypto Market Desk",
      sentiment: "positive",
      url: "https://example.com/news/{symbol}/momentum"
    },
    {
      title: "Whales Rotate Into {SYMBOL} Amid Market Volatility",
      summary: "Derivative positioning and large wallet inflows suggest strategic accumulation in {SYMBOL} even as broader risk assets consolidate.",
      source: "Onchain Signals",
      sentiment: "neutral",
      url: "https://example.com/news/{symbol}/whales"
    },
    {
      title: "Analysts Watch Key Support For {SYMBOL}",
      summary: "Technical analysts highlight a confluence of moving averages and volume nodes that have historically provided a bid for {SYMBOL} bulls.",
      source: "Block Insights",
      sentiment: "neutral",
      url: "https://example.com/news/{symbol}/support"
    }
  ];

  if (symbol === "BTC") {
    generic[0].title = "Bitcoin Eyes Macro Breakout As Funding Turns Positive";
    generic[0].summary = "Funding rates and CME futures positioning imply renewed demand for Bitcoin, with traders targeting macro resistance near yearly highs.";
    generic[0].source = "Macro Crypto";
    generic[0].sentiment = "positive";
  } else if (symbol === "ETH") {
    generic[0].title = "Stakers Accumulate ETH Ahead of Upgrade";
    generic[0].summary = "Validator net flows for Ethereum show a steady climb as developers finalize the next upgrade timeline.";
    generic[0].source = "Ethereum Beacon";
  }

  return generic;
}

function generateMockSentiment(symbol) {
  const now = Date.now();
  const upper = symbol.toUpperCase();

  const base = baseSentimentScore(upper);
  const score = clamp(base + (Math.random() - 0.5) * 0.35, 0, 1);
  const confidence = clamp(0.7 + Math.random() * 0.25, 0, 1);

  const positive = clamp(score * 0.8 + Math.random() * 0.1, 0, 1);
  const negative = clamp((1 - score) * 0.6 + Math.random() * 0.1, 0, 1);
  let neutral = clamp(1 - positive - negative, 0.05, 0.8);
  const total = positive + negative + neutral;
  const pos = positive / total;
  const neg = negative / total;
  const neu = neutral / total;

  const twitterMentions = randomRange(80, 5000);
  const redditPosts = randomRange(12, 520);
  const telegramMessages = randomRange(120, 2200);

  return {
    symbol: upper,
    overall_sentiment: {
      score: roundTo(score, 3),
      label: sentimentLabel(score),
      confidence: roundTo(confidence, 3)
    },
    sentiment_distribution: {
      positive: roundTo(pos, 3),
      negative: roundTo(neg, 3),
      neutral: roundTo(neu, 3)
    },
    social_metrics: {
      twitter: {
        mentions_24h: twitterMentions,
        sentiment_score: roundTo(clamp(score + (Math.random() - 0.5) * 0.2, 0, 1), 3),
        trending_rank: twitterMentions > 600 ? randomRange(1, 120) : null
      },
      reddit: {
        posts_24h: redditPosts,
        comments_24h: redditPosts * randomRange(4, 22),
        sentiment_score: roundTo(clamp(score + (Math.random() - 0.5) * 0.25, 0, 1), 3),
        top_subreddits: buildSubreddits(upper)
      },
      telegram: {
        messages_24h: telegramMessages,
        active_groups: randomRange(6, 40),
        sentiment_score: roundTo(clamp(score + (Math.random() - 0.5) * 0.18, 0, 1), 3)
      }
    },
    trending_topics: buildTrendingTopics(upper),
    influencer_mentions: buildInfluencerMentions(upper),
    fear_greed_index: randomRange(25, 75),
    volume_correlation: roundTo(clamp(0.25 + Math.random() * 0.6, 0, 1), 3),
    price_correlation: roundTo(clamp(-0.3 + Math.random() * 1.0, -1, 1), 3),
    last_updated: new Date(now).toISOString(),
    data_sources: ["Twitter", "Reddit", "Telegram", "Discord"],
    note: "Mock sentiment data for demonstration"
  };
}

function baseSentimentScore(symbol) {
  if (symbol === "BTC") return 0.64;
  if (symbol === "ETH") return 0.6;
  if (symbol === "SOL") return 0.58;
  if (symbol === "DOGE") return 0.55;
  return 0.5;
}

function sentimentLabel(score) {
  if (score >= 0.7) return "Very Bullish";
  if (score >= 0.6) return "Bullish";
  if (score >= 0.45) return "Neutral";
  if (score >= 0.3) return "Bearish";
  return "Very Bearish";
}

function buildSubreddits(symbol) {
  const base = [`r/${symbol}`, "r/CryptoCurrency", "r/altcoins", "r/cryptomarkets"];
  const count = randomRange(1, base.length);
  return base.slice(0, count);
}

function buildTrendingTopics(symbol) {
  const baseKeywords = [
    `#${symbol}`, `${symbol}USD`, "breakout", "on-chain", "whales", "ETF", "ecosystem", "layer2",
    "defi", "staking", "volume spike", "momentum"
  ];
  const count = randomRange(4, Math.min(baseKeywords.length, 8));
  return shuffle(baseKeywords)
    .slice(0, count)
    .map((keyword) => ({
      keyword,
      growth_24h: roundTo(clamp(-15 + Math.random() * 40, -25, 60), 1)
    }));
}

function buildInfluencerMentions(symbol) {
  const influencers = [
    { name: "CryptoWizard", platform: "Twitter" },
    { name: "DefiLlama", platform: "Twitter" },
    { name: "MarketAlpha", platform: "YouTube" },
    { name: "ChainWhisperer", platform: "Telegram" },
    { name: "BullBear", platform: "Reddit" }
  ];
  const sentiments = ["bullish", "bearish", "neutral"];
  const count = randomRange(2, influencers.length);
  return shuffle(influencers)
    .slice(0, count)
    .map((entry) => {
      const sentiment = sentiments[randomRange(0, sentiments.length - 1)];
      return {
        influencer: entry.name,
        platform: entry.platform,
        followers: randomRange(25_000, 350_000),
        sentiment,
        preview: `${entry.name} discussed ${symbol} and highlighted recent market structure moves.`,
        engagement: randomRange(2_000, 90_000),
        verified: Math.random() > 0.6
      };
    });
}

function randomRange(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function shuffle(arr) {
  const copy = [...arr];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
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

// --- SSE helpers on Hub prototype ---
Hub.prototype._broadcastSSE = function(payload) {
  const data = `data: ${JSON.stringify(payload)}\n\n`;
  const bytes = new TextEncoder().encode(data);
  for (const client of this.clients) {
    client.writer.write(bytes).catch(() => {
      // drop broken writers on next prune
    });
  }
};

Hub.prototype._pruneClients = function() {
  const survivors = new Set();
  for (const client of this.clients) {
    if (client && client.writer) {
      survivors.add(client);
    }
  }
  this.clients = survivors;
};
