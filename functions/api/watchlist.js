export async function onRequest({ env, request }) {
  const id = env.HUB.idFromName('global');
  const obj = env.HUB.get(id);
  const init = { method: request.method, headers: { 'content-type': 'application/json' } };
  if (request.method !== 'GET' && request.method !== 'HEAD') init.body = await request.text();
  return obj.fetch('https://do.internal/watchlist', init);
}
