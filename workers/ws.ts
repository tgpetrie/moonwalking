// SSE-based Worker for ultra-live crypto data (3-5s updates)
// Optimized for $5/month Cloudflare Workers Paid plan

export interface Env {
  HUB: DurableObjectNamespace;
  SNAPSHOTS_KV: KVNamespace;
  QUOTE?: string;
  DEBUG?: string;
  BACKEND_ORIGIN?: string;
}

const FETCH_MIN_MS = 3_000;             // 3s refresh while users connected (ULTRA LIVE)
const KV_PUT_MIN_MS = 10 * 60_000;      // 10min KV writes (protects quota)
const SSE_KEEPALIVE_MS = 20_000;        // 20s keepalive ping
const FALLBACK_MAX_AGE_MS = 5 * 60_000; // 5min max stale for KV fallback

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext) {
    const url = new URL(req.url);

    // CORS headers for development
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (req.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // SSE endpoint - real-time streaming
    if (url.pathname === '/api/events') {
      const id = env.HUB.idFromName('root');
      const hub = env.HUB.get(id);
      const response = await hub.fetch(new URL('/sse', url).toString(), req);
      return new Response(response.body, {
        ...response,
        headers: { ...Object.fromEntries(response.headers), ...corsHeaders }
      });
    }

    // Snapshot endpoints - for REST fallback
    if (url.pathname.includes('/api/component/gainers-table-1min') ||
        url.pathname.includes('/api/snapshots/gainers-1m')) {
      const id = env.HUB.idFromName('root');
      const hub = env.HUB.get(id);
      const r = await hub.fetch(new URL('/snapshot', url).toString(), req);

      if (r.ok) {
        return new Response(r.body, {
          ...r,
          headers: { ...Object.fromEntries(r.headers), ...corsHeaders }
        });
      }

      // KV fallback
      if (env.SNAPSHOTS_KV) {
        const raw: any = await env.SNAPSHOTS_KV.get('gainers-1m', { type: 'json' });
        if (raw && Date.now() - (raw.updatedAt ?? 0) <= FALLBACK_MAX_AGE_MS) {
          return json(raw, { headers: corsHeaders });
        }
      }

      return new Response('{}', { status: 503, headers: corsHeaders });
    }

    // One-hour price snapshot (for chart component)
    if (url.pathname.includes('/api/snapshots/one-hour-price') ||
        url.pathname.includes('/snapshots/one-hour-price')) {
      // Generate mock hourly price data
      // TODO: Replace with real historical data if available
      const now = Date.now();
      const prices = [];
      const basePrice = 50000; // Mock BTC price

      for (let i = 0; i < 60; i++) {
        prices.push({
          timestamp: now - (60 - i) * 60 * 1000,
          price: basePrice + Math.random() * 1000 - 500,
        });
      }

      return json({
        updatedAt: now,
        prices,
        symbol: 'BTC-USD',
      }, { headers: corsHeaders });
    }

    // Health check
    if (url.pathname === '/__health') {
      return json({ ok: true, mode: 'sse-live' }, { headers: corsHeaders });
    }

    return new Response('Not found', { status: 404, headers: corsHeaders });
  },

  // Cron every minute: keeps cache warm even with zero users
  async scheduled(_evt: ScheduledEvent, env: Env, ctx: ExecutionContext) {
    const id = env.HUB.idFromName('root');
    const hub = env.HUB.get(id);
    ctx.waitUntil(hub.fetch('https://do/scheduled'));
  }
};

function json(data: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(data), {
    ...init,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      ...(init.headers || {})
    },
  });
}

/* ---------- Durable Object (Hub) ---------- */

export class Hub {
  state: DurableObjectState;
  env: Env;

  // In-memory state (free, fast)
  #clients = new Set<WritableStreamDefaultWriter>();
  #snapshot: any = null;
  #lastFetch = 0;
  #lastKvPut = 0;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.env = env;
  }

  async fetch(req: Request) {
    const url = new URL(req.url);

    if (url.pathname.endsWith('/sse')) {
      return this.#handleSse();
    }

    if (url.pathname.endsWith('/snapshot')) {
      await this.#maybeTick(); // Ensure fresh
      return json(this.#snapshot ?? { rows: [], updatedAt: 0 });
    }

    if (url.pathname.endsWith('/scheduled')) {
      await this.#maybeTick(true); // Cron nudge
      return new Response('ok');
    }

    return new Response('not found', { status: 404 });
  }

  async #handleSse() {
    const { readable, writable } = new TransformStream();
    const writer = writable.getWriter();
    this.#clients.add(writer);

    // Immediately send current state
    await this.#send(writer, {
      type: 'hello',
      updatedAt: this.#snapshot?.updatedAt ?? 0,
      counts: {
        t1m: this.#snapshot?.rows?.length ?? 0,
        t3m: this.#snapshot?.rows?.length ?? 0,
        l3m: this.#snapshot?.rows?.length ?? 0,
      },
      v: 1,
    });

    // Trigger fresh fetch for active user
    this.#maybeTick().catch(() => {});

    // Keepalive interval
    const heartbeat = setInterval(() => {
      this.#send(writer, { type: 'keepalive', t: Date.now() }).catch(() => {
        clearInterval(heartbeat);
        this.#clients.delete(writer);
      });
    }, SSE_KEEPALIVE_MS);

    const headers = {
      'content-type': 'text/event-stream; charset=utf-8',
      'cache-control': 'no-cache, no-transform',
      'connection': 'keep-alive',
      'x-accel-buffering': 'no',
    };

    // Cleanup on disconnect
    const cleanup = () => {
      clearInterval(heartbeat);
      writer.close().catch(() => {});
      this.#clients.delete(writer);
      this.#log(`Client disconnected, ${this.#clients.size} remaining`);
    };

    return new Response(readable, {
      headers,
      status: 200,
    });
  }

  async #maybeTick(isCron = false) {
    const now = Date.now();
    const minGap = isCron ? 60_000 : FETCH_MIN_MS;

    if (now - this.#lastFetch < minGap) {
      this.#log(`Skip tick (too soon, gap=${now - this.#lastFetch}ms)`);
      return;
    }

    this.#lastFetch = now;
    this.#log(`Fetching fresh data (cron=${isCron}, clients=${this.#clients.size})`);

    const fresh = await this.#fetchFromSource().catch((err) => {
      this.#log('Fetch error:', err.message);
      return null;
    });

    if (!fresh) return;

    this.#snapshot = { ...fresh, updatedAt: Date.now() };

    // Broadcast to SSE clients (instant, free)
    this.#broadcast({
      type: 'state',
      updatedAt: this.#snapshot.updatedAt,
      counts: {
        t1m: this.#snapshot?.rows?.length ?? 0,
        t3m: this.#snapshot?.rows?.length ?? 0,
        l3m: this.#snapshot?.rows?.length ?? 0,
      },
      v: 1,
    });

    // Throttled KV writes (protects quota)
    if (this.env.SNAPSHOTS_KV && now - this.#lastKvPut >= KV_PUT_MIN_MS) {
      this.#lastKvPut = now;
      this.#log('Writing to KV');
      this.env.SNAPSHOTS_KV.put('gainers-1m', JSON.stringify(this.#snapshot), {
        expirationTtl: 3600
      }).catch((err) => {
        this.#log('KV write error:', err.message);
      });
    }
  }

  async #fetchFromSource(): Promise<any> {
    // Fetch from Coinbase API with retry logic
    const maxRetries = 2;

    for (let i = 0; i < maxRetries; i++) {
      try {
        // Get products and 24hr stats
        const productsUrl = 'https://api.exchange.coinbase.com/products';
        const r = await fetch(productsUrl, {
          headers: { 'Accept': 'application/json' },
          cf: { cacheTtl: 3, cacheEverything: true }
        });

        if (!r.ok) throw new Error(`HTTP ${r.status}`);

        const products: any[] = await r.json();

        // Filter USD pairs and calculate price changes
        const usdPairs = products
          .filter(p => p.quote_currency === 'USD' && p.status === 'online')
          .map(p => ({
            symbol: p.id,
            price: parseFloat(p.price || '0'),
            volume24h: parseFloat(p.volume_24h || '0'),
            priceChange24h: parseFloat(p.price_percentage_change_24h || '0'),
          }))
          .filter(p => p.volume24h > 100000) // Min volume filter
          .sort((a, b) => b.priceChange24h - a.priceChange24h) // Sort by gain
          .slice(0, 25); // Top 25

        this.#log(`Fetched ${usdPairs.length} gainers from Coinbase`);

        return { rows: usdPairs };

      } catch (err: any) {
        this.#log(`Fetch attempt ${i + 1} failed:`, err.message);
        if (i === maxRetries - 1) throw err;
        await new Promise(r => setTimeout(r, 1000 * (i + 1))); // Exponential backoff
      }
    }

    throw new Error('All fetch attempts failed');
  }

  #broadcast(msg: any) {
    const line = `data: ${JSON.stringify(msg)}\n\n`;
    const encoded = new TextEncoder().encode(line);

    this.#clients.forEach((w) => {
      w.write(encoded).catch(() => {
        this.#clients.delete(w);
      });
    });

    if (this.#clients.size > 0) {
      this.#log(`Broadcast to ${this.#clients.size} clients:`, msg.type);
    }
  }

  async #send(w: WritableStreamDefaultWriter, msg: any) {
    const line = `data: ${JSON.stringify(msg)}\n\n`;
    await w.write(new TextEncoder().encode(line));
  }

  #log(...args: any[]) {
    if (this.env.DEBUG === 'true') {
      console.log('[Hub]', ...args);
    }
  }
}
