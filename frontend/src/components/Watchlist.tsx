import React, { useCallback, useEffect, useMemo, useState } from 'react';
import TableShell, { TableRow } from './TableShell';
import { useWebSocket } from '../context/websocketcontext.jsx';

// Simple persistent store (localStorage) – can be replaced by backend later
const KEY = 'cbm_watchlist_v1';
interface StoredItem { symbol:string; priceAtAdd:number; addedAt:number }

function load(): StoredItem[] {
  try { return JSON.parse(localStorage.getItem(KEY)||'[]'); } catch { return []; }
}
function save(items: StoredItem[]) {
  try { localStorage.setItem(KEY, JSON.stringify(items)); } catch {}
}

// Legacy write helper used by older tests which expect 'watchlist_symbols'
function saveLegacy(items: StoredItem[]) {
  try { localStorage.setItem('watchlist_symbols', JSON.stringify(items.map(i=>i.symbol.toUpperCase()))); } catch {}
}

export default function Watchlist({ initialSymbols }:{ initialSymbols?: string[] } = {}){
  const { latestData } = useWebSocket();
  const [items, setItems] = useState<StoredItem[]>(()=> {
    const saved = load();
    if (saved.length) return saved;
    if (initialSymbols && initialSymbols.length) return initialSymbols.map(s=>({ symbol: s.replace(/-USD$/i,'').toLowerCase(), priceAtAdd: 0, addedAt: Date.now() }));
    return [];
  });
  const [loading,setLoading] = useState(false);

  // Sync storage events (multi-tab)
  useEffect(()=>{
    function onStorage(e: StorageEvent){ if (e.key===KEY) setItems(load()); }
    window.addEventListener('storage', onStorage);
    return ()=> window.removeEventListener('storage', onStorage);
  }, []);

  const latestPrices: Record<string, any> = latestData?.prices || {};
  const rows: TableRow[] = useMemo(()=> items.map((w,i)=>{
    const entry = latestPrices[w.symbol+'-USD'];
    let curr = w.priceAtAdd;
    if (entry != null){
      if (typeof entry === 'number') curr = entry; else if (typeof entry === 'object') curr = entry.price ?? entry.current ?? entry.last ?? curr;
    }
    const pct = w.priceAtAdd ? ((curr - w.priceAtAdd)/w.priceAtAdd)*100 : 0;
    return { rank:i+1, symbol:w.symbol.toUpperCase(), price:'$'+curr.toFixed(4), pct:(pct>=0?'+':'')+pct.toFixed(2)+'%' };
  }), [items, latestPrices]);

  const add = useCallback((symbol:string)=>{
    setItems(prev=>{
      if (prev.find(p=> p.symbol===symbol.toLowerCase())) return prev;
      const entry = latestPrices[symbol.toUpperCase()+'-USD'] || latestPrices[symbol.toLowerCase()+'-USD'];
      let price = 0; if (entry) price = typeof entry==='number'? entry : (entry.price ?? entry.current ?? entry.last ?? 0);
      const next = [...prev, { symbol: symbol.toLowerCase(), priceAtAdd: price, addedAt: Date.now() }];
      save(next); saveLegacy(next); return next;
    });
  }, [latestPrices]);
  const remove = useCallback((symbol:string)=>{
    setItems(prev=>{ const next = prev.filter(p=> p.symbol!==symbol.toLowerCase()); save(next); saveLegacy(next); return next; });
  }, []);

  // Expose quick keyboard add (optional future) – stub for now
  useEffect(()=>{ /* could wire command palette */ }, []);

  // Provide simple UI for adding/removing at top (inline controls)
  const Controls = (
    <div className="flex gap-2 flex-wrap mb-2 text-xs">
      <form onSubmit={e=>{ e.preventDefault(); const fd=new FormData(e.currentTarget); const sym=(fd.get('sym') as string||'').trim(); if(sym) add(sym); e.currentTarget.reset(); }} className="flex gap-1">
        <input name="sym" aria-label="Add symbol" placeholder="Add symbol" className="px-2 py-1 bg-white/5 rounded border border-white/10 focus:outline-none focus:ring-2 focus:ring-purple-400 w-24" />
        <button className="px-2 py-1 bg-gradient-to-r from-purple-500/70 to-pink-500/70 rounded text-white hover:from-purple-500 hover:to-pink-500 transition-colors">Add</button>
      </form>
      {items.length>0 && <span className="opacity-60 self-center">{items.length} tracked</span>}
    </div>
  );

  return (
    <div>
      {Controls}
      <TableShell
        variant='gainers'
        title='Watchlist'
        rows={rows}
        columns={{ pctLabel:'% chg', showPrice:true }}
        loading={loading}
        emptyMessage='Use the form above to add symbols to your watchlist.'
      />
      {/* For legacy tests: log visible symbols and persist legacy key */}
      <LogAndPersistLegacy items={items} />
      {rows.length>0 && (
        <div className="mt-2 flex flex-wrap gap-1 text-[10px]">
          {rows.map(r=> (
            <button key={'chip'+r.symbol} onClick={()=> remove(r.symbol)} className="px-2 py-1 bg-white/10 hover:bg-white/20 rounded-full">
              {r.symbol} ×
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function LogAndPersistLegacy({ items }:{ items:StoredItem[] }){
  useEffect(()=>{
    try {
      saveLegacy(items);
      if (typeof console !== 'undefined' && console.log) console.log('Watchlist visible symbols:', items.map(i=>i.symbol.toUpperCase()).join(', '))
    } catch {}
  }, [items])
  return null
}
