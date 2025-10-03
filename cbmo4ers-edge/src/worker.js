// Cloudflare Worker + Durable Object for 1h volume banner cache
// Minimal, self-contained; relies on an upstream slim endpoint for seeding

// ------- config -------
const SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "ADA-USD"]; // extend as needed
const RING_MINUTES = 60;
const EDGE_SMAXAGE = 20; // seconds

// ------- helpers -------
const nowISO = () => new Date().toISOString();
const toNum = (v, d = null) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
};
const corsHeaders = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "access-control-allow-headers": "content-type",
};

// ------- Durable Object -------
export class VolRing {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.buffer = {}; // { [symbol]: [{ts, volume_24h, volume_change_1h_pct?}] }
    this.lastMinuteWritten = 0;
  }

  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response("", { headers: corsHeaders });
    }

    if (path === "/ring/push" && request.method === "POST") {
      const { snapshot = {}, ts = nowISO() } = await request.json();
      const t = Date.parse(ts);
      const minuteBucket = Math.floor(t / 60000);
      if (minuteBucket === this.lastMinuteWritten) {
        return new Response(JSON.stringify({ ok: true, deduped: true }), { status: 200, headers: corsHeaders });
      }
      this.lastMinuteWritten = minuteBucket;

      for (const sym of Object.keys(snapshot)) {
        const vol = toNum(snapshot[sym]?.volume_24h);
        if (!Number.isFinite(vol)) continue;
        if (!this.buffer[sym]) this.buffer[sym] = [];
        const arr = this.buffer[sym];
        arr.push({ ts: t, volume_24h: vol, volume_change_1h_pct: toNum(snapshot[sym]?.volume_change_1h_pct, null) });
        while (arr.length > RING_MINUTES) arr.shift();
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: corsHeaders });
    }

    if (path === "/ring/read" && request.method === "GET") {
      const syms = Object.keys(this.buffer).length ? Object.keys(this.buffer) : SYMBOLS;
      const out = syms.map((sym) => {
        const arr = this.buffer[sym] || [];
        const latest = arr[arr.length - 1] || null;
        if (!latest) {
          return { symbol: sym, ts: nowISO(), volume_24h: null, volume_change_1h_pct: null, volume_change_estimate: null, estimated: false };
        }
        const oneHourAgoTs = latest.ts - 60 * 60000;
        let ago = null;
        for (let i = 0; i < arr.length; i++) {
          if (arr[i].ts <= oneHourAgoTs) ago = arr[i];
          else break;
        }
        const base = {
          symbol: sym,
          ts: new Date(latest.ts).toISOString(),
          volume_24h: latest.volume_24h,
          volume_change_1h_pct: latest.volume_change_1h_pct ?? null,
          volume_change_estimate: null,
          estimated: false,
        };
        if (base.volume_change_1h_pct == null && ago?.volume_24h != null && ago.volume_24h > 0) {
          const delta = latest.volume_24h - ago.volume_24h;
          const pct = (delta / ago.volume_24h) * 100;
          base.volume_change_estimate = Number(pct.toFixed(3));
          base.estimated = true;
        }
        return base;
      });
      out.sort((a, b) => (Number(b.volume_change_1h_pct ?? b.volume_change_estimate ?? -Infinity) - Number(a.volume_change_1h_pct ?? a.volume_change_estimate ?? -Infinity)));
      return new Response(JSON.stringify({ rows: out }, null, 2), { headers: { "content-type": "application/json; charset=utf-8", ...corsHeaders } });
    }

    return new Response("VolRing endpoint not found", { status: 404, headers: corsHeaders });
  }
}

// ------- Worker -------
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response("", { headers: corsHeaders });
    if (url.pathname === "/api/health") return new Response(JSON.stringify({ ok: true, service: "cbmo4ers-edge" }), { headers: { "content-type": "application/json", ...corsHeaders } });
    if (url.pathname !== "/api/component/bottom-banner-scroll") return new Response("Not found", { status: 404, headers: corsHeaders });

    const cache = caches.default;
    const cached = await cache.match(request);
    if (cached) return cached;

    const id = env.VOL_RING.idFromName("global-ring");
    const stub = env.VOL_RING.get(id);
    const ringResp = await stub.fetch(new Request(new URL("/ring/read", request.url), { method: "GET" }));
    const body = await ringResp.text();

    const resp = new Response(body, { headers: { "content-type": "application/json; charset=utf-8", "cache-control": `public, s-maxage=${EDGE_SMAXAGE}`, ...corsHeaders } });
    ctx.waitUntil(cache.put(request, resp.clone()));
    return resp;
  },

  async scheduled(event, env, ctx) {
    try {
      const res = await fetch(env.UPSTREAM_URL, { cf: { cacheTtl: 0, cacheEverything: false } });
      if (!res.ok) throw new Error(`Upstream ${res.status}`);
      const data = await res.json();
      const snapshot = {};
      const accept = (sym, obj) => {
        const vol = toNum(obj?.volume_24h ?? obj?.volume ?? obj?.vol_24h);
        if (!Number.isFinite(vol)) return;
        snapshot[sym] = { volume_24h: vol, volume_change_1h_pct: toNum(obj?.volume_change_1h_pct, null) };
      };
      if (Array.isArray(data)) for (const row of data) if (row?.symbol) accept(row.symbol, row);
      if (Array.isArray(data?.rows)) for (const row of data.rows) if (row?.symbol) accept(row.symbol, row);
      if (Array.isArray(data?.banner)) for (const row of data.banner) if (row?.symbol) accept(row.symbol, row);
      for (const k of Object.keys(data || {})) { const v = data[k]; if (v && typeof v === "object" && ("volume_24h" in v || "vol_24h" in v || "volume" in v)) accept(k, v); }
      for (const group of ["stats", "volumes"]) { const m = data?.[group]; if (m && typeof m === "object") for (const k of Object.keys(m)) accept(k, m[k]); }

      const id = env.VOL_RING.idFromName("global-ring");
      const stub = env.VOL_RING.get(id);
      await stub.fetch(new Request(new URL("/ring/push", "http://vol-ring.internal"), { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ snapshot, ts: new Date().toISOString() }) }));
    } catch (err) {
      console.error("cron error:", err);
    }
  },
};

