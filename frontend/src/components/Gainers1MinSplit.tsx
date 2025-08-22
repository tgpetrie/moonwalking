import React, { useMemo, useRef } from 'react';
import TableShell from './TableShell';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { useRowFlash } from '../utils/useRowFlash';

interface RawItem { symbol: string; price: number; delta_1m: number; peak?: number }

export default function Gainers1MinSplit(){
  const { latestData } = useWebSocket();
  const list: RawItem[] = useMemo(()=>{
    if (latestData?.t1m && Array.isArray(latestData.t1m)) return latestData.t1m.slice(0,8);
    if (latestData?.prices){
      const arr = Object.keys(latestData.prices).map((s,i)=>({
        symbol: s.replace('-USD',''),
        price: latestData.prices[s].price || 0,
        delta_1m: latestData.prices[s].change || 0
      }));
      return arr.sort((a,b)=> b.delta_1m - a.delta_1m).slice(0,8);
    }
    return [];
  }, [latestData]);

  const flashes = useRowFlash(list, r=> r.delta_1m);
  const seenRef = useRef<Set<string>>(new Set());
  const rows = useMemo(()=> list
    .sort((a,b)=> b.delta_1m - a.delta_1m)
    .map((r,i)=>{
      const isNew = !seenRef.current.has(r.symbol);
      return { rank: i+1, symbol: r.symbol.toUpperCase(), price: '$'+r.price.toFixed(2), pct: (r.delta_1m>=0?'+':'') + (r.delta_1m*100).toFixed(2)+'%', peak:r.peak, isNew, flash: flashes.get(r.symbol) };
    }), [list, flashes]);
  rows.forEach(r=> seenRef.current.add(r.symbol));

  const left = rows.slice(0,4), right = rows.slice(4,8);
  const avgPct = rows.length? (rows.reduce((a,r)=> a + parseFloat(r.pct),0)/rows.length).toFixed(2)+'%':'—';

  const loading = !latestData || left.length===0;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <TableShell variant="gainers" title="1–4 Minute Gainers" totalPct={avgPct} rows={left} columns={{ pctLabel:'1m %' }} loading={loading} emptyMessage="No 1m gainers yet" />
      <TableShell variant="gainers" title="5–8 Minute Gainers" totalPct={avgPct} rows={right} columns={{ pctLabel:'1m %' }} loading={loading} emptyMessage="No 1m gainers yet" />
    </div>
  );
}
