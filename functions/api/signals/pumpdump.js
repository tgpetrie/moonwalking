export async function onRequest({ env }) {
  const origin = env.BACKEND_ORIGIN || 'http://localhost:5001';
  const res = await fetch(`${origin.replace(/\/$/, '')}/api/signals/pumpdump`);
  return new Response(await res.text(), {
    status: res.status,
    headers: {
      'content-type': res.headers.get('content-type') || 'application/json',
      'cache-control': 's-maxage=5, stale-while-revalidate=20'
    }
  });
}

