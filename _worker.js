/**
 * Cloudflare Pages Advanced Mode Worker
 * Routes /api/** requests to Worker via HTTP
 * Serves static assets for everything else
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Route /api/** to the Worker via HTTP fetch
    if (url.pathname.startsWith("/api/")) {
      // Strip /api prefix and forward to Worker
      const workerPath = url.pathname.replace(/^\/api/, "") || "/";
      const workerUrl = new URL(workerPath + url.search, "https://mw-hub.tgpetrie.workers.dev");

      // Clone request for Worker
      const init = {
        method: request.method,
        headers: request.headers,
        body: ["GET", "HEAD"].includes(request.method)
          ? undefined
          : await request.arrayBuffer(),
      };

      // Fetch from Worker and return response
      const response = await fetch(workerUrl, init);

      // Add CORS headers
      const newResponse = new Response(response.body, response);
      newResponse.headers.set("Access-Control-Allow-Origin", "*");
      newResponse.headers.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
      newResponse.headers.set("Access-Control-Allow-Headers", "Content-Type");

      return newResponse;
    }

    // Serve static assets from Pages
    return env.ASSETS.fetch(request);
  },
};
