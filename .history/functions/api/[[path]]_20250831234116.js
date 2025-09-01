// Catch-all (optional) Pages Function for /api/* routes.
// Cloudflare Pages parameter syntax forbids '...'; use double brackets [[path]] for optional splat.
// BACKEND_ORIGIN should be set in project env (e.g., https://your-backend.example.com).

export async function onRequest(context) {
  const backend = context.env.BACKEND_ORIGIN;
  if (!backend) {
    return new Response(JSON.stringify({ error: 'Backend not configured' }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const url = new URL(context.request.url);
  // Strip /api prefix so /api/foo/bar -> /foo/bar when proxying to backend /api
  const stripped = url.pathname.replace(/^\/api/, '') || '/';
  const target = `${backend.replace(/\/$/, '')}/api${stripped}${url.search}`;

  const init = {
    method: context.request.method,
    headers: context.request.headers,
    body: ['GET', 'HEAD'].includes(context.request.method)
      ? undefined
      : await context.request.arrayBuffer()
  };

  try {
    const resp = await fetch(target, init);
    const headers = new Headers(resp.headers);
    return new Response(resp.body, { status: resp.status, headers });
  } catch (e) {
    return new Response(JSON.stringify({ error: 'Upstream fetch failed' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
