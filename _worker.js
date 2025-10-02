/**
 * Cloudflare Pages Advanced Mode Worker
 * Proxies /api/** to Worker (same-origin, no CORS)
 * WebSocket proxy ready for paid tier upgrade
 * Serves static assets for everything else
 */

const WORKER_URL = "https://mw-hub.tgpetrie.workers.dev";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Proxy REST API to Worker
    if (url.pathname.startsWith("/api/")) {
      const workerPath = url.pathname.replace(/^\/api/, "") || "/";
      const workerUrl = new URL(workerPath + url.search, WORKER_URL);

      const init = {
        method: request.method,
        headers: request.headers,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      };

      return fetch(workerUrl, init);
    }

    // WebSocket proxy (REQUIRES PAID PLAN - Cloudflare free tier doesn't support WebSocket in Workers)
    // Uncomment when upgraded from free tier:
    /*
    if (url.pathname === "/ws") {
      if (request.headers.get("Upgrade") !== "websocket") {
        return new Response("Expected WebSocket", { status: 426 });
      }

      const workerUrl = new URL("/ws", WORKER_URL);
      return fetch(workerUrl, request);
    }
    */

    // Serve static assets
    return env.ASSETS.fetch(request);
  },
};
