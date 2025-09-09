// functions/api/[[path]].js
export async function onRequest({ request, env }) {
  const incoming = new URL(request.url);
  const upstream = new URL(env.BACKEND_ORIGIN); // e.g., http://127.0.0.1:8787
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
  return new Response(resp.body, { status: resp.status, headers: resp.headers });
}
