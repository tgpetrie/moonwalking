export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const p = url.pathname;

    if (p === "/server-info") {
      return json({ ok: true, service: "worker", t: Date.now() });
    }

    if (p === "/watchlist") {
      if (req.method === "GET")  return getWatchlist(req, env);
      if (req.method === "POST") return saveWatchlist(req, env);
      return new Response("Method Not Allowed", { status: 405 });
    }

    if (p === "/codex") {
      if (req.method === "GET")  return getCodex(req, env);
      if (req.method === "POST") return saveCodex(req, env);
      return new Response("Method Not Allowed", { status: 405 });
    }

    return new Response("Not Found", { status: 404 });
  }
};

function userKey(req) {
  return req.headers.get("x-user") || "dev-user";
}
function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json" }
  });
}

/* ---- Watchlist (KV) ---- */
async function getWatchlist(req, env) {
  const user = userKey(req);
  const data = await env.WATCHLIST_KV.get(`wl:${user}`, "json");
  return json({ ok: true, watchlist: data?.symbols ?? [] });
}
async function saveWatchlist(req, env) {
  const user = userKey(req);
  const body = await req.json().catch(() => ({}));
  const symbols = Array.isArray(body.symbols) ? body.symbols : [];
  await env.WATCHLIST_KV.put(
    `wl:${user}`,
    JSON.stringify({ symbols, updatedAt: Date.now() })
  );
  return json({ ok: true, saved: symbols.length });
}

/* ---- Codex (KV) ---- */
async function getCodex(req, env) {
  const user = userKey(req);
  const codex = await env.WATCHLIST_KV.get(`codex:${user}`, "json");
  return json({ ok: true, codex: codex ?? { lists: {}, notes: {} } });
}
async function saveCodex(req, env) {
  const user = userKey(req);
  const incoming = await req.json().catch(() => ({}));
  const prev = (await env.WATCHLIST_KV.get(`codex:${user}`, "json")) ?? { lists: {}, notes: {} };
  const merged = deepMerge(prev, incoming);
  await env.WATCHLIST_KV.put(`codex:${user}`, JSON.stringify(merged));
  return json({ ok: true });
}
function deepMerge(a, b) {
  if (Array.isArray(a) && Array.isArray(b)) return b;
  if (a && typeof a === "object" && b && typeof b === "object") {
    const out = { ...a };
    for (const k of Object.keys(b)) out[k] = deepMerge(a[k], b[k]);
    return out;
  }
  return b ?? a;
}
