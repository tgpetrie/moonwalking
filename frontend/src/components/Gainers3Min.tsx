import React, { useMemo } from 'react';
import TableShell from './TableShell';
import { useWebSocket } from '../context/websocketcontext.jsx';
import { useRowFlash } from '../utils/useRowFlash';

interface Raw { symbol:string; price:number; delta_3m:number; peak?:number }

export default function Gainers3Min(){
  const { latestData } = useWebSocket();
  const list: Raw[] = useMemo(()=> Array.isArray(latestData?.t3m)? latestData.t3m.slice(0,8): [], [latestData]);
  const flashes = useRowFlash(list, r=> r.delta_3m);
  const rows = useMemo(()=> list
    .sort((a,b)=> b.delta_3m - a.delta_3m)
    .map((r,i)=> ({ rank:i+1, symbol:r.symbol.toUpperCase(), price:'$'+r.price.toFixed(2), pct:(r.delta_3m>=0?'+':'')+(r.delta_3m*100).toFixed(2)+'%', peak:r.peak, flash: flashes.get(r.symbol) })), [list, flashes]);
  const headline = rows.length? rows[0].pct:'—';
  const loading = !latestData || rows.length===0;
  return <TableShell variant='gainers' title='3-Minute Gainers' totalPct={headline} rows={rows} columns={{ pctLabel:'3m %' }} loading={loading} emptyMessage='No 3m gainers yet' />
}
