// functions/api.js - Handles /api/* requests
export async function onRequest({ request, env }) {
  const incoming = new URL(request.url);

  // Simple test response first
  if (incoming.pathname === "/api/server-info") {
    return new Response(JSON.stringify({
      ok: true,
      service: "pages-function",
      timestamp: Date.now()
    }), {
      headers: { "content-type": "application/json" }
    });
  }

  // For other API routes, proxy to backend
  if (!env.BACKEND_ORIGIN) {
    return new Response(JSON.stringify({
      ok: false,
      error: "BACKEND_ORIGIN missing",
      hint: "set -b BACKEND_ORIGIN=http://127.0.0.1:8787"
    }), {
      status: 500,
      headers: { "content-type": "application/json" },
    });
  }

  const origin = new URL(env.BACKEND_ORIGIN);
  const upstream = new URL(origin.toString());
  // Forward everything after /api to the upstream root
  upstream.pathname = incoming.pathname.replace(/^\/api/, "");
  upstream.search = incoming.search;

  // Clone headers and strip hop-by-hop ones that can cause issues
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");

  const init = { method: request.method, headers, redirect: "manual" };
  if (!["GET", "HEAD"].includes(request.method)) {
    // Preserve body for non-idempotent requests
    init.body = request.body;
  }

  // Let websocket upgrades pass through untouched
  if ((request.headers.get("upgrade") || "").toLowerCase() === "websocket") {
    return fetch(upstream.toString(), init);
  }

  // Regular HTTP fetch proxy
  return fetch(upstream.toString(), init);
}
