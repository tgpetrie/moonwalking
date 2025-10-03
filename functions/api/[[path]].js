// functions/api/[[path]].js
export async function onRequest({ request, env }) {
  if (!env.BACKEND_ORIGIN) {
    return new Response(JSON.stringify({ ok:false, error:"BACKEND_ORIGIN missing" }), {
      status: 500, headers: { "content-type": "application/json" }
    });
  }
  const incoming = new URL(request.url);

  // If the client requests the SSE endpoint, proxy it directly to the Worker/DO
  if (incoming.pathname === '/api/events') {
    const workerOrigin = env.WORKER_ORIGIN || env.WORKER_URL || 'http://127.0.0.1:8787';
    const target = new URL(workerOrigin);
    target.pathname = '/api/events';
    target.search = incoming.search;

    const init = {
      method: request.method,
      headers: new Headers(request.headers),
      redirect: 'manual',
    };
    init.headers.delete('host');
    if (!['GET','HEAD'].includes(request.method)) init.body = await request.arrayBuffer();

    const resp = await fetch(target, init);
    const outHeaders = new Headers(resp.headers);
    outHeaders.set('access-control-allow-origin', '*');
    outHeaders.set('access-control-allow-headers', '*');
    outHeaders.set('access-control-allow-methods', 'GET,POST,OPTIONS');
    outHeaders.set('x-proxy', 'functions-events-proxy');
    return new Response(resp.body, { status: resp.status, headers: outHeaders });
  }

  const upstream = new URL(env.BACKEND_ORIGIN); // e.g., http://127.0.0.1:5001
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
