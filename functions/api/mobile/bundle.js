export async function onRequest({ env }) {
  // Build bundle from Durable Object snapshots for fast, free caching at the edge
  const id = env.HUB.idFromName("global");
  const stub = env.HUB.get(id);
  try {
    const res = await stub.fetch("https://do/snapshots");
    const snap = await res.json();
    const now = Date.now();

    const pick = (arr, mapFn) => Array.isArray(arr) ? arr.slice(0, 30).map(mapFn) : [];

    const banner1h = pick(snap.topBanner, it => ({
      symbol: it.symbol,
      price: Number(it.current_price || 0),
      changePct1h: Number(it.price_change_1h || 0),
      ts: now,
    }));

    const gainers1m = pick(snap.t1m, it => ({
      symbol: it.symbol,
      price: Number(it.current_price || 0),
      changePct1m: Number(it.price_change_percentage_1min || 0),
      ts: now,
    }));

    const gainers3m = pick(snap.t3m, it => ({
      symbol: it.symbol,
      price: Number(it.current_price || 0),
      changePct3m: Number(it.price_change_percentage_3min || 0),
      ts: now,
    }));

    // losers derived from 3m by ascending change
    const losers3m = Array.isArray(snap.t3m)
      ? snap.t3m
          .slice()
          .filter(x => typeof x.price_change_percentage_3min === 'number')
          .sort((a,b) => a.price_change_percentage_3min - b.price_change_percentage_3min)
          .slice(0, 30)
          .map(it => ({ symbol: it.symbol, price: Number(it.current_price||0), changePct3m: Number(it.price_change_percentage_3min||0), ts: now }))
      : [];

    const volume1h = pick(snap.bottomBanner, it => ({
      symbol: it.symbol,
      price: Number(it.current_price || 0),
      volumeChangePct1h: Number(it.volume_change_1h_pct || 0),
      ts: now,
    }));

    const out = { banner1h, gainers1m, gainers3m, losers3m, volume1h, ts: now };
    return new Response(JSON.stringify(out), {
      headers: { 'content-type': 'application/json', 'cache-control': 's-maxage=8, stale-while-revalidate=20' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ banner1h: [], gainers1m: [], gainers3m: [], losers3m: [], volume1h: [], ts: Date.now() }), {
      headers: { 'content-type': 'application/json' }, status: 200
    });
  }
}

