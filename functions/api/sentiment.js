export async function onRequest({ env, request }) {
  const id = env.HUB.idFromName('global');
  const obj = env.HUB.get(id);
  const url = new URL(request.url);
  const symbols = url.searchParams.get('symbols') || '';
  const doUrl = new URL('https://do.internal/sentiment');
  if (symbols) doUrl.searchParams.set('symbols', symbols);
  return obj.fetch(doUrl.toString());
}
