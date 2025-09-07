export async function onRequest({ env }) {
  // DO exposes 3m losers via /component/losers-table
  const id = env.HUB.idFromName("global");
  const stub = env.HUB.get(id);
  const res = await stub.fetch("https://do/component/losers-table");
  return new Response(await res.text(), {
    headers: { "content-type": "application/json", "cache-control": "s-maxage=10, stale-while-revalidate=30" }
  });
}

