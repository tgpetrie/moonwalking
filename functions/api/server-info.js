/ **
 * GET /api/server-info
 * Proxies to the Durable Object to report runtime/health info.
 * Requires the DO binding "HUB" to be configured in Pages > Functions.
 */
export async function onRequestGet({ env }) {
  // Resolve a stable DO instance by name
  const id = env.HUB.idFromName("hub");
  const stub = env.HUB.get(id);

  // Ask the DO for server info
  const doResp = await stub.fetch("https://do/server-info", {
    headers: { accept: "application/json" },
  });

  const headers = new Headers(doResp.headers);
  headers.set("cache-control", "no-store");
  headers.set("content-type", "application/json");

  return new Response(await doResp.text(), {
    status: doResp.status,
    headers,
  });
}
/**
 * GET /api/server-info
 * Proxies to the Durable Object to report runtime/health info.
 * Requires the DO binding "HUB" to be configured in Pages > Functions.
 */
export async function onRequestGet({ env }) {
  // Resolve a stable DO instance by name
  const id = env.HUB.idFromName("hub");
  const stub = env.HUB.get(id);

  // Ask the DO for server info
  const doResp = await stub.fetch("https://do/server-info", {
    headers: { accept: "application/json" },
  });

  const headers = new Headers(doResp.headers);
  headers.set("cache-control", "no-store");
  headers.set("content-type", "application/json");

  return new Response(await doResp.text(), {
    status: doResp.status,
    headers,
  });
}