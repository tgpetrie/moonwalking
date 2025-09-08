export async function onRequest({ env, request }) {
  const id = env.HUB.idFromName('global');
  const obj = env.HUB.get(id);

  const u = new URL(request.url);
  const doPath = u.pathname.replace(/^\/api/, '') || '/';
  const doUrl = new URL('https://do.internal' + doPath);
  u.searchParams.forEach((v, k) => doUrl.searchParams.set(k, v));

  const init = {
    method: request.method,
    headers: request.headers,
    body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer(),
  };

  const res = await obj.fetch(doUrl.toString(), init);
  const headers = new Headers(res.headers);
  if (!headers.get('content-type')) headers.set('content-type', 'application/json');
  return new Response(res.body, { status: res.status, headers });
}
