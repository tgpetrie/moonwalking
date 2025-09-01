export async function onRequest({ env }) {
  const id = env.HUB.idFromName("global");
  const stub = env.HUB.get(id);
  const res = await stub.fetch("https://do/component/gainers-table-1min");
  return new Response(await res.text(), {
    headers: { "content-type": "application/json", "cache-control": "s-maxage=10, stale-while-revalidate=30" }
  });
}

