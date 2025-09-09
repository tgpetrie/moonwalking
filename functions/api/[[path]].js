// functions/api/[[path]].js
export async function onRequest({ request, env }) {
  const origin = env.BACKEND_ORIGIN || env.BACKEND_URL; // fallback name
  if (!origin) {
    return new Response(JSON.stringify({ ok:false, error:"BACKEND_ORIGIN missing" }), {
      status: 500, headers: { "content-type": "application/json" }
    });
  }

  const incoming = new URL(request.url);
  const upstream = new URL(origin); // e.g., http://127.0.0.1:8787
  upstream.pathname = incoming.pathname.replace(/^\/api/, "");
  upstream.search = incoming.search;

  const init = {
    method: request.method,
    headers: new Headers(request.headers),
    redirect: "manual",
  };
  init.headers.delete("host");
  // Make CLI tests happy; browsers don't care either way
  init.headers.set("accept-encoding", "identity");

  if (!["GET","HEAD"].includes(request.method)) {
    init.body = await request.arrayBuffer();
  }

  const resp = await fetch(upstream, init);
  const headers = new Headers(resp.headers);
  headers.set("x-proxy", "root-functions");
  return new Response(resp.body, { status: resp.status, headers });
}
