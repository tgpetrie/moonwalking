import React, { useMemo } from 'react';
import TableShell from './TableShell';
import { useWebSocket } from '../context/websocketcontext.jsx';

interface Watch { symbol:string; priceAtAdd:number; addedAt:number }

export default function Watchlist(){
  const { latestData } = useWebSocket();
  const watch: Watch[] = [];// integrate with real store later
  const latestPrices: Record<string, any> = latestData?.prices || {};
  const rows = useMemo(()=> watch.map((w,i)=>{
    const entry = latestPrices[w.symbol+'-USD'];
    let curr = w.priceAtAdd;
    if (entry != null){
      if (typeof entry === 'number') curr = entry; else if (typeof entry === 'object') curr = entry.price ?? entry.current ?? entry.last ?? curr;
    }
    const pct = w.priceAtAdd ? ((curr - w.priceAtAdd)/w.priceAtAdd)*100 : 0;
    return { rank:i+1, symbol:w.symbol.toUpperCase(), price:'$'+curr.toFixed(2), pct:(pct>=0?'+':'')+pct.toFixed(2)+'%' };
  }), [watch, latestPrices]);
  return <TableShell variant='gainers' title='Watchlist' rows={rows} columns={{ pctLabel:'% chg' }} />
}
