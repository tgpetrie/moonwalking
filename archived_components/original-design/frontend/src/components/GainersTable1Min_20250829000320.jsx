import React from 'react';
import UniformCard from './UniformCard.jsx';

export default function GainersTable1MinHistoric({ items = [] }) {
  const top = Array.isArray(items) ? items.slice(0, 8) : [];
  return (
    <div className="panel">
      <div className="gainers-tiles">
        {top.map((r, i) => (
          <UniformCard key={r.symbol} symbol={r.symbol} price={r.price} change={r.change} rank={i+1} windowLabel="1-min" />
        ))}
      </div>
    </div>
  );
}
