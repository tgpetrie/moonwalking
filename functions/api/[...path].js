export async function onRequest(context) {
  // Proxy API calls via Pages Functions when using same-origin relative mode
  // Configure BACKEND_ORIGIN in Cloudflare Pages project settings
  const backend = context.env.BACKEND_ORIGIN;
  if (!backend) {
    return new Response(
      JSON.stringify({ error: 'Backend not configured' }),
      { status: 502, headers: { 'Content-Type': 'application/json' } }
    );
  }

  const url = new URL(context.request.url);
  // Incoming path will be /api/... because of _redirects rule; strip the /functions prefix if present
  const pathname = url.pathname
    .replace(/^\/functions\/api/, '')
    .replace(/^\/api\/?/, '/');

  const target = `${backend.replace(/\/$/, '')}/api${pathname}${url.search}`;

  const init = {
    method: context.request.method,
    headers: context.request.headers,
    body: ['GET', 'HEAD'].includes(context.request.method)
      ? undefined
      : await context.request.arrayBuffer()
  };

  const resp = await fetch(target, init);
  // Pass through status and headers
  return new Response(resp.body, { status: resp.status, headers: resp.headers });
}