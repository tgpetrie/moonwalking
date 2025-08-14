export async function onRequest(context) {
  // Optional: proxy API calls via Pages Functions if VITE_API_URL=relative
  // Set BACKEND_ORIGIN as a Pages env var if you want to proxy
  const backend = context.env.BACKEND_ORIGIN;
  if (!backend) {
    return new Response(JSON.stringify({ error: 'Backend not configured' }), { status: 502, headers: { 'Content-Type': 'application/json' } });
  }
  const url = new URL(context.request.url);
  const target = `${backend.replace(/\/$/, '')}/api${url.pathname.replace(/^\/functions\/api/, '')}${url.search}`;
  const init = {
    method: context.request.method,
    headers: context.request.headers,
    body: ['GET','HEAD'].includes(context.request.method) ? undefined : await context.request.text()
  };
  const resp = await fetch(target, init);
  return new Response(resp.body, { status: resp.status, headers: resp.headers });
}
