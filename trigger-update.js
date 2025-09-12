// Manual trigger for data updates (since scheduled workers don't run in local dev)
const coins = "BTC,ETH,SOL,ADA,DOT,LINK,AVAX,MATIC,ATOM,NEAR,UNI,AAVE,CRV,COMP,MKR,SNX,YFI,SUSHI,1INCH,BAL".split(',');

async function updateSnapshots() {
  try {
    const now = Date.now();
    console.log('Fetching prices for', coins.length, 'coins...');
    
    const results = await Promise.all(coins.map(async (sym) => {
      try {
        const res = await fetch(`https://api.exchange.coinbase.com/products/${sym}-USD/ticker`, { 
          headers: { 'user-agent': 'mw-hub/1.0' }
        });
        if (!res.ok) return null;
        const j = await res.json();
        const price = Number(j?.price);
        if (!Number.isFinite(price)) return null;
        return { symbol: sym, price };
      } catch (e) { 
        console.log(`Error fetching ${sym}:`, e.message);
        return null; 
      }
    }));
    const rows = results.filter(Boolean);
    console.log('Got prices for', rows.length, 'coins');

    // Get previous data to maintain history
    const prevResp = await fetch("http://127.0.0.1:8787/snapshots");
    const prev = prevResp.ok ? await prevResp.json() : {};
    const prevHistory = prev && prev.history ? prev.history : {};
    
    // Build price history
    const history = { ...prevHistory };
    for (const r of rows) {
      const arr = (history[r.symbol] || []).slice(-5);
      arr.push({ t: now, p: r.price });
      arr.sort((a,b)=>a.t-b.t);
      while (arr.length > 6) arr.shift();
      history[r.symbol] = arr;
    }

    // Calculate changes
    const lookback = (arr, ms) => {
      const target = now - ms;
      let best = null;
      for (const pt of arr) { if (pt.t <= target) best = pt; else break; }
      return best;
    };

    const t1mRaw = [], t3mRaw = [];
    for (const r of rows) {
      const arr = history[r.symbol] || [];
      const pNow = r.price;
      const p1 = lookback(arr, 60_000);
      const p3 = lookback(arr, 180_000);
      const c1 = (p1 && p1.p > 0) ? ((pNow - p1.p) / p1.p) * 100 : 0;
      const c3 = (p3 && p3.p > 0) ? ((pNow - p3.p) / p3.p) * 100 : 0;
      t1mRaw.push({ symbol: r.symbol, current_price: pNow, price_change_percentage_1min: c1 });
      t3mRaw.push({ symbol: r.symbol, current_price: pNow, price_change_percentage_3min: c3 });
    }
    
    const sortDesc = (arr, key) => arr.slice().sort((a,b)=>Math.abs(b[key]) - Math.abs(a[key])).map((it, i)=>({ rank: i+1, ...it }));
    const t1m = sortDesc(t1mRaw, 'price_change_percentage_1min');
    const t3m = sortDesc(t3mRaw, 'price_change_percentage_3min');
    const topBanner = t1m.slice(0, 20).map(it => ({ rank: it.rank, symbol: it.symbol, current_price: it.current_price, price_change_1h: it.price_change_percentage_1min }));
    const bottomBanner = t3m.slice(0, 20).map(it => ({ rank: it.rank, symbol: it.symbol, current_price: it.current_price, volume_change_1h_pct: 0, volume_24h: 0 }));

    console.log('Updating snapshots...');
    const updateResp = await fetch("http://127.0.0.1:8787/snapshots", {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ topBanner, bottomBanner, t1m, t3m, alerts: [], history })
    });
    
    const result = await updateResp.json();
    console.log('Update result:', result);
    console.log(`Generated ${t1m.length} 1m entries, ${t3m.length} 3m entries`);
  } catch (e) {
    console.error('Update failed:', e);
  }
}

// Run immediately and then every 30 seconds
updateSnapshots();
setInterval(updateSnapshots, 30000);

console.log('Data update trigger started. Press Ctrl+C to stop.');