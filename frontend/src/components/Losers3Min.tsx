import React, { useMemo } from 'react';
import TableShell from './TableShell';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { useRowFlash } from '../utils/useRowFlash';

interface Raw { symbol:string; price:number; delta_3m:number; peak?:number }

export default function Losers3Min(){
  const { latestData } = useWebSocket();
  const list: Raw[] = useMemo(()=> Array.isArray(latestData?.t3m)? latestData.t3m.slice(0,8): [], [latestData]);
  const flashes = useRowFlash(list, r=> r.delta_3m);
  const rows = useMemo(()=> list
    .filter(r=> r.delta_3m <= 0)
    .sort((a,b)=> a.delta_3m - b.delta_3m)
    .slice(0,8)
    .map((r,i)=> ({ rank:i+1, symbol:r.symbol.toUpperCase(), price:'$'+r.price.toFixed(2), pct:(r.delta_3m>=0?'+':'')+(r.delta_3m*100).toFixed(2)+'%', peak:r.peak, flash: flashes.get(r.symbol) })), [list, flashes]);
  const headline = rows.length? rows[0].pct:'—';
  return <TableShell variant='losers' title='3-Minute Losers' totalPct={headline} rows={rows} columns={{ pctLabel:'3m %' }} />
}
